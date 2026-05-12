"""Token-bucket rate limiter per pool.

Soft cap on order_send rate. `try_acquire()` returns False without
blocking when the bucket is empty so the caller can fail-fast and the
queue worker keeps draining.
"""

from __future__ import annotations

import threading
import time


class TokenBucket:
    def __init__(self, rate_per_s: float, burst: int):
        self.rate = max(0.0, rate_per_s)
        self.capacity = max(1, burst)
        self._tokens = float(self.capacity)
        self._last = time.monotonic()
        self._lock = threading.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last
        self._last = now
        self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)

    def try_acquire(self, n: float = 1.0) -> bool:
        with self._lock:
            self._refill()
            if self._tokens >= n:
                self._tokens -= n
                return True
            return False

    def available(self) -> float:
        with self._lock:
            self._refill()
            return self._tokens
