"""Copy recovery configuration with hardcoded defaults + system_settings override.

Defaults are chosen to be safe; admins can override via the existing system_settings
table (single-row settings) by setting recovery_* JSON keys (future extension).
For this phase, all values are read directly from environment-tunable defaults.
"""

from __future__ import annotations
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class RecoveryConfig:
    # OPEN
    max_retry_attempts_open: int = int(os.getenv("RECOVERY_MAX_OPEN_ATTEMPTS", "1"))
    retry_window_seconds_open: int = int(os.getenv("RECOVERY_OPEN_WINDOW_S", "20"))
    favorable_limit_points_forex: int = int(os.getenv("RECOVERY_FAVORABLE_FOREX_PTS", "80"))
    favorable_limit_points_gold: int = int(os.getenv("RECOVERY_FAVORABLE_GOLD_PTS", "300"))
    favorable_limit_points_default: int = int(os.getenv("RECOVERY_FAVORABLE_DEFAULT_PTS", "150"))

    # CLOSE
    max_retry_attempts_close: int = int(os.getenv("RECOVERY_MAX_CLOSE_ATTEMPTS", "3"))
    retry_window_seconds_close: int = int(os.getenv("RECOVERY_CLOSE_WINDOW_S", "30"))
    close_retry_independent_of_price: bool = True
    close_retry_delay_ms: int = int(os.getenv("RECOVERY_CLOSE_DELAY_MS", "300"))


_config: RecoveryConfig | None = None


def get_recovery_config() -> RecoveryConfig:
    global _config
    if _config is None:
        _config = RecoveryConfig()
    return _config


def favorable_limit_for_symbol(symbol: str) -> int:
    """Return favorable-move tolerance (in points) for a given symbol."""
    cfg = get_recovery_config()
    s = (symbol or "").upper()
    if "XAU" in s or "GOLD" in s:
        return cfg.favorable_limit_points_gold
    # Forex pairs: 6 letters, no digits, e.g. EURUSD
    if len(s) == 6 and s.isalpha():
        return cfg.favorable_limit_points_forex
    return cfg.favorable_limit_points_default


# ── Fatal reason codes (do not retry CLOSE) ─────────────────────
CLOSE_FATAL_REASON_CODES = {
    "account_disconnected",
    "market_closed",
    "symbol_not_found",
    "trade_disabled",
    "no_trade_permission",
    "invalid_position_structure",
}


def is_fatal_for_close(reason_code: str | None, error_message: str | None) -> bool:
    if reason_code in CLOSE_FATAL_REASON_CODES:
        return True
    msg = (error_message or "").lower()
    if any(k in msg for k in ("market is closed", "trade disabled", "not allowed", "invalid symbol")):
        return True
    return False
