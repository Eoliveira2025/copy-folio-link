"""Login per-account session.

The MT5 python package uses a single terminal process and a single logged-in
account at a time. We serialize per-account access with a lock and keep track
of the currently logged-in login to avoid redundant logins.
"""
from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional

from app.mt5 import terminal_manager
from app.utils.logger import get_logger

log = get_logger("mt5.session")

try:
    import MetaTrader5 as mt5  # type: ignore
except Exception:  # pragma: no cover
    mt5 = None  # type: ignore


@dataclass
class SessionInfo:
    login: int
    server: str
    last_used: float


_global_lock = threading.Lock()
_current: Optional[SessionInfo] = None


@contextmanager
def login_account(login: str, server: Optional[str], password: Optional[str]):
    """Login into an MT5 account, yielding the mt5 module while locked."""
    if not terminal_manager.initialize():
        raise RuntimeError("mt5 terminal not initialized")

    login_int = int(login)
    with _global_lock:
        global _current
        need_login = (
            _current is None
            or _current.login != login_int
            or (server and _current.server != server)
        )
        if need_login:
            if not password:
                raise RuntimeError(f"missing password for login {login}")
            ok = mt5.login(login=login_int, server=server or "", password=password)  # type: ignore[union-attr]
            if not ok:
                err = mt5.last_error()  # type: ignore[union-attr]
                raise RuntimeError(f"mt5.login failed for {login}: {err}")
            _current = SessionInfo(login=login_int, server=server or "", last_used=time.time())
            log.info("logged in MT5 account %s @ %s", login_int, server)
        else:
            _current.last_used = time.time()
        try:
            yield mt5
        finally:
            pass


def current_session() -> Optional[SessionInfo]:
    return _current
