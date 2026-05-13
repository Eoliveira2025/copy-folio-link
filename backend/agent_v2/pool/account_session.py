"""AccountSession — serialized login per terminal/pool.

Invariants:
  * Exactly one account is "current" per terminal at any time.
  * `acquire(account_id)` blocks until the terminal lock is held AND the
    requested account is logged in. Release returns the lock.
  * Sticky: re-acquiring the *same* account skips the (slow) re-login.
  * Session has a TTL; expired sessions are re-logged on next acquire.
  * DRY-RUN by default: no real `mt5.initialize/login` call. The login
    cost is simulated so latency metrics work.

Real MT5 login lands in increment 6 (OrderExecutor).
"""

from __future__ import annotations

import os
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional, Callable
from uuid import UUID

from ..config import get_v2_settings
from ..utils.logger import get_logger
from ..utils.security import decrypt_mt5_password
from .repo import AccountDetails


# Toggle real MT5 login from env. Default: dry-run.
_DRY_RUN_ENV = "V2_SESSION_DRY_RUN"


def _is_dry_run() -> bool:
    val = os.environ.get(_DRY_RUN_ENV, "true").strip().lower()
    return val not in ("0", "false", "no")


@dataclass
class _SessionState:
    account_id: Optional[UUID] = None
    logged_in_at: float = 0.0  # monotonic seconds
    login_count: int = 0


class LoginFailedError(RuntimeError):
    pass


class AccountSession:
    """Per-terminal serialized login + execution gate.

    One instance per (pool_id, terminal_id). Construct it once and share
    among queue workers — the internal lock guarantees exclusivity.
    """

    def __init__(
        self,
        *,
        pool_id: UUID,
        terminal_id: UUID,
        terminal_path: str,
        account_details_loader: Callable[[UUID], Optional[AccountDetails]],
        session_ttl_s: float = 600.0,
        sticky_hold_ms: Optional[int] = None,
    ):
        self.pool_id = pool_id
        self.terminal_id = terminal_id
        self.terminal_path = terminal_path
        self.account_details_loader = account_details_loader
        self.session_ttl_s = session_ttl_s
        self.settings = get_v2_settings()
        self.sticky_hold_ms = (
            sticky_hold_ms
            if sticky_hold_ms is not None
            else self.settings.SESSION_STICKY_HOLD_MS
        )
        self._lock = threading.RLock()
        self._state = _SessionState()
        self.log = get_logger("session").bind(
            pool_id=str(pool_id),
            terminal_id=str(terminal_id),
        )

    # ── core ──────────────────────────────────────────────────────
    def _is_session_fresh(self, account_id: UUID) -> bool:
        if self._state.account_id != account_id:
            return False
        age = time.monotonic() - self._state.logged_in_at
        return age < self.session_ttl_s

    def _do_login(self, account_id: UUID, login: int) -> float:
        """Returns login_latency_ms. Raises LoginFailedError on failure."""
        t0 = time.monotonic()
        if _dry_run():
            # Simulate ~1s login cost (kept small for tests).
            time.sleep(0.05)
        else:  # pragma: no cover — real MT5 lands in increment 6
            try:
                import MetaTrader5 as mt5  # type: ignore
            except Exception as e:
                raise LoginFailedError(f"MetaTrader5 import failed: {e}")
            try:
                mt5.shutdown()
            except Exception:
                pass
            ok = mt5.initialize(
                path=os.path.join(self.terminal_path, "terminal64.exe"),
                timeout=self.settings.SESSION_LOGIN_TIMEOUT_S * 1000,
            )
            if not ok:
                raise LoginFailedError(
                    f"mt5.initialize failed: {mt5.last_error()}"
                )
        latency_ms = (time.monotonic() - t0) * 1000.0
        self._state.account_id = account_id
        self._state.logged_in_at = time.monotonic()
        self._state.login_count += 1
        return latency_ms

    @contextmanager
    def acquire(self, *, account_id: UUID, login: int):
        """Hold the terminal for the given account.

        Yields a small dict with login_latency_ms (0 if sticky).
        """
        log = self.log.bind(account_id=str(account_id))
        acquired = self._lock.acquire(timeout=self.settings.SESSION_LOGIN_TIMEOUT_S)
        if not acquired:
            log.error("session lock timeout", extra={"action": "session_acquire_timeout"})
            raise LoginFailedError("session lock timeout")
        try:
            login_latency_ms = 0.0
            switched = False
            if self._is_session_fresh(account_id):
                log.info(
                    "session sticky reuse",
                    extra={"action": "session_reuse"},
                )
            else:
                try:
                    login_latency_ms = self._do_login(account_id, login)
                    switched = True
                    log.info(
                        "session login ok",
                        extra={
                            "action": "session_login",
                            "latency_ms": round(login_latency_ms, 2),
                            "dry_run": _dry_run(),
                        },
                    )
                except LoginFailedError as e:
                    log.error(
                        "session login failed",
                        extra={"action": "session_login_failed"},
                        exc_info=e,
                    )
                    raise
            yield {
                "login_latency_ms": login_latency_ms,
                "switched": switched,
                "login_count": self._state.login_count,
            }
            # Sticky hold: keep account "warm" briefly so back-to-back
            # tasks of the same account reuse the session.
            if self.sticky_hold_ms > 0:
                time.sleep(self.sticky_hold_ms / 1000.0)
        finally:
            self._lock.release()

    # ── introspection ─────────────────────────────────────────────
    def current_account(self) -> Optional[UUID]:
        return self._state.account_id

    def login_count(self) -> int:
        return self._state.login_count
