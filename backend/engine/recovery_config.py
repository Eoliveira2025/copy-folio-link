"""Copy recovery configuration.

Layered resolution (per key):
  1. Override from `system_settings.recovery_overrides` (JSONB) — admin-tunable
  2. Environment variable
  3. Hardcoded default

DB overrides are read with a short TTL cache (default 30s) so admins can change
limits without restarting the engine, while keeping decision-path latency low.

Recognised override keys (flat, dotted):
  copy.retry.open.max_attempts
  copy.retry.open.retry_window_seconds
  copy.retry.open.favorable_limit_points.forex
  copy.retry.open.favorable_limit_points.gold
  copy.retry.open.favorable_limit_points.default
  copy.retry.close.max_attempts
  copy.retry.close.retry_window_seconds
"""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger("engine.recovery_config")


# ── Hardcoded defaults (env-tunable) ─────────────────────────────
def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


_DEFAULTS: dict[str, int] = {
    "copy.retry.open.max_attempts": _env_int("RECOVERY_MAX_OPEN_ATTEMPTS", 1),
    "copy.retry.open.retry_window_seconds": _env_int("RECOVERY_OPEN_WINDOW_S", 20),
    "copy.retry.open.favorable_limit_points.forex": _env_int("RECOVERY_FAVORABLE_FOREX_PTS", 80),
    "copy.retry.open.favorable_limit_points.gold": _env_int("RECOVERY_FAVORABLE_GOLD_PTS", 300),
    "copy.retry.open.favorable_limit_points.default": _env_int("RECOVERY_FAVORABLE_DEFAULT_PTS", 150),
    "copy.retry.close.max_attempts": _env_int("RECOVERY_MAX_CLOSE_ATTEMPTS", 3),
    "copy.retry.close.retry_window_seconds": _env_int("RECOVERY_CLOSE_WINDOW_S", 30),
}

# Non-overridable internals
_CLOSE_RETRY_INDEPENDENT_OF_PRICE = True
_CLOSE_RETRY_DELAY_MS = _env_int("RECOVERY_CLOSE_DELAY_MS", 300)

_CACHE_TTL_S = _env_int("RECOVERY_CONFIG_CACHE_TTL_S", 30)


@dataclass(frozen=True)
class RecoveryConfig:
    max_retry_attempts_open: int
    retry_window_seconds_open: int
    favorable_limit_points_forex: int
    favorable_limit_points_gold: int
    favorable_limit_points_default: int

    max_retry_attempts_close: int
    retry_window_seconds_close: int
    close_retry_independent_of_price: bool = _CLOSE_RETRY_INDEPENDENT_OF_PRICE
    close_retry_delay_ms: int = _CLOSE_RETRY_DELAY_MS


# ── DB override loader (cached, lazy) ────────────────────────────
_lock = threading.Lock()
_cached_cfg: Optional[RecoveryConfig] = None
_cached_at: float = 0.0


def _coerce_int(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except Exception:
        return fallback


def _load_overrides_from_db() -> dict:
    """Best-effort read of system_settings.recovery_overrides. Never raises."""
    try:
        # Lazy imports to avoid cycles and keep this module import-cheap
        from sqlalchemy import create_engine, text
        from engine.config import get_engine_settings

        settings = get_engine_settings()
        eng = create_engine(settings.DATABASE_URL_SYNC, pool_pre_ping=True, pool_size=1, max_overflow=0)
        with eng.connect() as conn:
            row = conn.execute(
                text("SELECT recovery_overrides FROM system_settings LIMIT 1")
            ).fetchone()
        if row and isinstance(row[0], dict):
            return row[0]
        return {}
    except Exception as e:
        logger.debug(f"recovery_overrides DB read skipped: {e}")
        return {}


def _resolve(key: str, overrides: dict) -> int:
    if key in overrides and overrides[key] is not None:
        return _coerce_int(overrides[key], _DEFAULTS[key])
    return _DEFAULTS[key]


def _build_config(overrides: dict) -> RecoveryConfig:
    return RecoveryConfig(
        max_retry_attempts_open=_resolve("copy.retry.open.max_attempts", overrides),
        retry_window_seconds_open=_resolve("copy.retry.open.retry_window_seconds", overrides),
        favorable_limit_points_forex=_resolve("copy.retry.open.favorable_limit_points.forex", overrides),
        favorable_limit_points_gold=_resolve("copy.retry.open.favorable_limit_points.gold", overrides),
        favorable_limit_points_default=_resolve("copy.retry.open.favorable_limit_points.default", overrides),
        max_retry_attempts_close=_resolve("copy.retry.close.max_attempts", overrides),
        retry_window_seconds_close=_resolve("copy.retry.close.retry_window_seconds", overrides),
    )


def get_recovery_config(force_refresh: bool = False) -> RecoveryConfig:
    """Return current effective config, refreshing from DB at most every TTL seconds."""
    global _cached_cfg, _cached_at
    now = time.time()
    with _lock:
        if (
            not force_refresh
            and _cached_cfg is not None
            and (now - _cached_at) < _CACHE_TTL_S
        ):
            return _cached_cfg
        overrides = _load_overrides_from_db()
        _cached_cfg = _build_config(overrides)
        _cached_at = now
        return _cached_cfg


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
