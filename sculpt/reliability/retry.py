"""Retry logic with exponential backoff."""

import asyncio
import random
from functools import wraps
from typing import Any, Callable, TypeVar, Optional

from ..models import GenerationParams, ModelName
from .breaker import CircuitBreaker, BreakerState
from .limiter import TokenBucket


T = TypeVar('T')


class RetryExhausted(Exception):
    """Raised when all retry attempts exhausted."""
    def __init__(self, last_error: Exception, attempts: int):
        self.last_error = last_error
        self.attempts = attempts
        super().__init__(f"Retry exhausted after {attempts} attempts: {last_error}")


class TransientError(Exception):
    """Error that should trigger a retry."""
    pass


async def with_retry(
    fn: Callable[..., T],
    *args,
    attempts: int = 4,
    base_delay: float = 1.0,
    max_delay: float = 120.0,
    exponential_base: float = 5.0,
    retry_on: tuple = (TransientError, TimeoutError, ConnectionError),
    **kwargs
) -> T:
    """
    Execute function with exponential backoff retry.
    
    Delays: 1s, 5s, 25s, 125s... (capped at max_delay)
    """
    last_error = None
    
    for attempt in range(attempts):
        try:
            return await fn(*args, **kwargs)
        except retry_on as e:
            last_error = e
            if attempt == attempts - 1:
                raise RetryExhausted(e, attempts)
            
            delay = min(base_delay * (exponential_base ** attempt), max_delay)
            # Add jitter (±20%)
            delay *= random.uniform(0.8, 1.2)
            
            await asyncio.sleep(delay)
        except Exception as e:
            # Non-retryable error - raise immediately
            raise
    
    raise RetryExhausted(last_error or Exception("Unknown error"), attempts)


async def execute_with_reliability(
    adapter,
    input_path,
    params: "GenerationParams",
    breaker: "CircuitBreaker",
    limiter: "TokenBucket",
    max_attempts: int = 4,
    input_type: str = "image"
):
    """
    Execute generation with full reliability stack:
    - Token bucket rate limiting
    - Circuit breaker
    - Exponential backoff retry
    """
    from ..models import GenerationResult, InputType
    import time
    from ..output import OutputManager
    from ..config import config
    from ..models import InputType as InputTypeEnum
    
    # Check circuit breaker
    breaker.check_transition()
    if breaker.state != "closed":
        raise TransientError(f"Circuit breaker {breaker.state} for {adapter.name}")
    
    # Acquire rate limit token
    await limiter.acquire()
    
    output_manager = OutputManager(config.output_dir)
    
    async def _generate():
        start = time.time()
        # Adapter.generate is async, await it directly
        result_path = await adapter.generate(input_path, params)
        inference_time = time.time() - start
        
        # Save output
        final_path = output_manager.save(result_path, input_path, adapter.name, params)
        
        return GenerationResult(
            local_path=final_path,
            model_used=adapter.name,
            input_type=InputTypeEnum(input_type),
            inference_seconds=inference_time,
        )
    
    try:
        result = await with_retry(
            _generate,
            attempts=max_attempts,
            base_delay=1.0,
            retry_on=(TransientError, TimeoutError, ConnectionError)
        )
        breaker.record_success()
        return result
    except Exception as e:
        breaker.record_failure()
        raise