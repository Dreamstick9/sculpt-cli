"""Token bucket rate limiter per Space."""

import asyncio
import time
from collections import deque
from typing import Optional


class TokenBucket:
    """Token bucket rate limiter for per-Space request limiting."""
    
    def __init__(self, rate_per_minute: int):
        self.rate_per_minute = rate_per_minute
        self.tokens = float(rate_per_minute)
        self.last_refill = time.time()
        self._lock = asyncio.Lock()
    
    async def acquire(self, tokens: int = 1) -> None:
        """Acquire tokens, waiting if necessary."""
        async with self._lock:
            while self.tokens < tokens:
                await self._refill()
                if self.tokens < tokens:
                    wait_time = (tokens - self.tokens) * (60.0 / self.rate_per_minute)
                    await asyncio.sleep(wait_time)
                else:
                    break
            self.tokens -= tokens
    
    async def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill
        new_tokens = elapsed * (self.rate_per_minute / 60.0)
        self.tokens = min(self.rate_per_minute, self.tokens + new_tokens)
        self.last_refill = now
    
    def try_acquire(self, tokens: int = 1) -> bool:
        """Try to acquire tokens without blocking. Returns True if successful."""
        self._refill_sync()
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False
    
    def _refill_sync(self) -> None:
        now = time.time()
        elapsed = now - self.last_refill
        new_tokens = elapsed * (self.rate_per_minute / 60.0)
        self.tokens = min(self.rate_per_minute, self.tokens + new_tokens)
        self.last_refill = now