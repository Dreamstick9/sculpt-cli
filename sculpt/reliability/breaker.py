"""Circuit breaker for model adapters."""

import time
from enum import Enum
from typing import Optional


class BreakerState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """
    Circuit breaker pattern for model adapters.
    
    CLOSED → normal operation
    OPEN → skip this adapter entirely
    HALF_OPEN → send 1 probe request to test
    """
    
    def __init__(
        self, 
        threshold: int = 5, 
        window_seconds: int = 300,
        half_open_timeout: int = 60
    ):
        self.threshold = threshold
        self.window_seconds = window_seconds
        self.half_open_timeout = half_open_timeout
        
        self.state = BreakerState.CLOSED
        self.failures: list[float] = []  # timestamps
        self.last_state_change = time.time()
        self.success_count = 0
    
    def record_success(self) -> None:
        """Record a successful call."""
        if self.state == BreakerState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= 1:  # 1 success closes it
                self._close()
        self.failures = [t for t in self.failures 
                        if time.time() - t < self.window_seconds]
    
    def record_failure(self) -> None:
        """Record a failed call."""
        now = time.time()
        self.failures.append(now)
        self.failures = [t for t in self.failures 
                        if now - t < self.window_seconds]
        
        if self.state == BreakerState.CLOSED:
            if len(self.failures) >= self.threshold:
                self._open()
        elif self.state == BreakerState.HALF_OPEN:
            self._open()
    
    def _open(self) -> None:
        """Transition to OPEN state."""
        self.state = BreakerState.OPEN
        self.last_state_change = time.time()
        self.success_count = 0
    
    def _close(self) -> None:
        """Transition to CLOSED state."""
        self.state = BreakerState.CLOSED
        self.last_state_change = time.time()
        self.failures.clear()
        self.success_count = 0
    
    def check_transition(self) -> None:
        """Check if should transition from OPEN to HALF_OPEN."""
        if self.state == BreakerState.OPEN:
            if time.time() - self.last_state_change >= self.half_open_timeout:
                self.state = BreakerState.HALF_OPEN
                self.success_count = 0