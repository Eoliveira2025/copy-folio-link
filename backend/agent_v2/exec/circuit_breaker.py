"""Circuit breaker per pool.

Counts consecutive failures of `mt5.order_send` (or earlier validation
errors that imply a sick terminal). When the threshold is reached the
pool is marked FAILED and no further executions are allowed until an
operator resets it.
"""

from __future__ import annotations

import threading
from typing import Callable, Optional
from uuid import UUID

from ..config import get_v2_settings
from ..utils.logger import get_logger


class CircuitBreaker:
    def __init__(
        self,
        *,
        pool_id: UUID,
        pool_name: str,
        on_trip: Optional[Callable[[], None]] = None,
        threshold: Optional[int] = None,
    ):
        s = get_v2_settings()
        self.pool_id = pool_id
        self.pool_name = pool_name
        self.threshold = threshold or s.POOL_CB_FAILURE_THRESHOLD
        self.reset_on_success = s.POOL_CB_RESET_AFTER_SUCCESS
        self._lock = threading.Lock()
        self._consecutive_failures = 0
        self._tripped = False
        self._on_trip = on_trip
        self.log = get_logger("circuit_breaker").bind(
            pool_id=str(pool_id), pool_name=pool_name,
        )

    @property
    def tripped(self) -> bool:
        return self._tripped

    def is_open(self) -> bool:
        """Return True when the breaker is OPEN (executions forbidden)."""
        return self._tripped

    def record_success(self) -> None:
        with self._lock:
            if self.reset_on_success and self._consecutive_failures > 0:
                self._consecutive_failures = 0

    def record_failure(self, reason: str) -> bool:
        """Returns True if this failure tripped the breaker."""
        with self._lock:
            if self._tripped:
                return False
            self._consecutive_failures += 1
            if self._consecutive_failures >= self.threshold:
                self._tripped = True
                self.log.error(
                    "circuit breaker tripped",
                    extra={
                        "action": "circuit_breaker_tripped",
                        "consecutive_failures": self._consecutive_failures,
                        "reason": reason,
                    },
                )
                if self._on_trip:
                    try:
                        self._on_trip()
                    except Exception as e:
                        self.log.error(
                            "circuit breaker on_trip handler failed",
                            extra={"action": "circuit_breaker_on_trip_failed"},
                            exc_info=e,
                        )
                return True
        return False

    def reset(self) -> None:
        with self._lock:
            self._consecutive_failures = 0
            self._tripped = False
        self.log.info("circuit breaker reset", extra={"action": "circuit_breaker_reset"})
