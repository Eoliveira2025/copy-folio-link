"""AccountContext — represents a single MT5 account's state and context within a terminal."""

import time
from dataclasses import dataclass, field
from typing import Optional, Dict
from uuid import UUID
from ..utils.logger import get_logger

@dataclass
class AccountContext:
    """In-memory state for one MT5 account session."""
    account_id: UUID
    login: int
    server: str
    
    # State
    is_logged_in: bool = False
    last_login_attempt: float = 0
    last_success_at: float = 0
    failure_count: int = 0
    last_error: Optional[str] = None
    
    # Metrics
    login_latency_ms: float = 0
    total_trades: int = 0
    failed_trades: int = 0
    
    def __post_init__(self):
        self.log = get_logger("account_context").bind(
            account_id=str(self.account_id),
            login=self.login
        )

    def mark_login_success(self, latency_ms: float):
        self.is_logged_in = True
        self.last_login_attempt = time.time()
        self.last_success_at = time.time()
        self.failure_count = 0
        self.last_error = None
        self.login_latency_ms = latency_ms
        self.log.info("account login success", extra={"latency_ms": round(latency_ms, 2)})

    def mark_login_failure(self, error: str):
        self.is_logged_in = False
        self.last_login_attempt = time.time()
        self.failure_count += 1
        self.last_error = error
        self.log.error("account login failure", extra={"error": error, "failures": self.failure_count})

    def should_retry_login(self) -> bool:
        """Backoff logic for retries."""
        if self.is_logged_in:
            return False
            
        # Stop after too many consecutive failures (account_blocked / failed_credentials)
        if self.failure_count > 10:
            return False
            
        now = time.time()
        # Exponential backoff: 2s, 4s, 8s, ..., max 300s
        wait = min(2 ** self.failure_count, 300)
        return (now - self.last_login_attempt) > wait

    def get_metrics(self) -> Dict:
        return {
            "is_logged_in": self.is_logged_in,
            "failure_count": self.failure_count,
            "last_error": self.last_error,
            "login_latency_ms": self.login_latency_ms,
            "total_trades": self.total_trades,
            "failed_trades": self.failed_trades
        }
