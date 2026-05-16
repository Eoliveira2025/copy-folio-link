"""Initialize the MT5 terminal process."""
from __future__ import annotations

import threading

from app.config import settings
from app.utils.logger import get_logger

log = get_logger("mt5.terminal")

try:
    import MetaTrader5 as mt5  # type: ignore
except Exception:  # pragma: no cover - not on Windows
    mt5 = None  # type: ignore

_lock = threading.Lock()
_initialized = False


def is_available() -> bool:
    return mt5 is not None


def initialize() -> bool:
    """Initialize the terminal once. Returns True if MT5 is usable."""
    global _initialized
    if not is_available():
        log.warning("MetaTrader5 package not available (non-Windows env?)")
        return False
    with _lock:
        if _initialized:
            return True
        ok = mt5.initialize(path=settings.mt5_terminal_path)  # type: ignore[union-attr]
        if not ok:
            log.error("mt5.initialize failed: %s", mt5.last_error())  # type: ignore[union-attr]
            return False
        _initialized = True
        log.info("MT5 terminal initialized at %s", settings.mt5_terminal_path)
        return True


def shutdown() -> None:
    global _initialized
    if not is_available():
        return
    with _lock:
        if _initialized:
            mt5.shutdown()  # type: ignore[union-attr]
            _initialized = False
