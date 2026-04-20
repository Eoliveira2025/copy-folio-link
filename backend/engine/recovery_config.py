"""Copy recovery configuration.

Layered resolution (per key):
  1. Override from `system_settings.recovery_overrides` (JSONB) — admin-tunable
  2. Environment variable
  3. Hardcoded default

DB overrides are read with a short TTL cache (default 30s) so admins can change
limits without restarting the engine, while keeping decision-path latency low.

Canonical nested override schema (stored in `system_settings.recovery_overrides`):

    {
      "open": {
        "max_attempts": 1,
        "retry_window_seconds": 20,
        "favorable_limit_points": {
          "forex": 80,
          "gold": 300,
          "default": 100
        }
      },
      "close": {
        "max_attempts": 3,
        "retry_window_seconds": 30
      }
    }

Backward compatibility: a legacy flat/dotted format is also accepted, e.g.:
    {"copy.retry.open.max_attempts": 2, "copy.retry.close.max_attempts": 5}

Resolution rules:
- If overrides is null / not a dict / fails to parse → log warning, use defaults.
- Each leaf is type-validated; invalid leaves are ignored (warning logged once).
- Missing keys fall back through env → hardcoded.
- CLOSE never depends on price.
- OPEN continues to use the copier account tick (decided in the worker).
- `no_position_to_close` remains an informative event, not a critical error.
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


# Canonical (nested) keys → defaults. Path uses tuple of keys into the nested dict.
_DEFAULTS: dict[tuple[str, ...], int] = {
    ("open", "max_attempts"): _env_int("RECOVERY_MAX_OPEN_ATTEMPTS", 1),
    ("open", "retry_window_seconds"): _env_int("RECOVERY_OPEN_WINDOW_S", 20),
    ("open", "favorable_limit_points", "forex"): _env_int("RECOVERY_FAVORABLE_FOREX_PTS", 80),
    ("open", "favorable_limit_points", "gold"): _env_int("RECOVERY_FAVORABLE_GOLD_PTS", 300),
    ("open", "favorable_limit_points", "default"): _env_int("RECOVERY_FAVORABLE_DEFAULT_PTS", 150),
    ("close", "max_attempts"): _env_int("RECOVERY_MAX_CLOSE_ATTEMPTS", 3),
    ("close", "retry_window_seconds"): _env_int("RECOVERY_CLOSE_WINDOW_S", 30),
}

# Map legacy flat (dotted) keys → canonical nested path, for backward compatibility.
_LEGACY_FLAT_MAP: dict[str, tuple[str, ...]] = {
    "copy.retry.open.max_attempts": ("open", "max_attempts"),
    "copy.retry.open.retry_window_seconds": ("open", "retry_window_seconds"),
    "copy.retry.open.favorable_limit_points.forex": ("open", "favorable_limit_points", "forex"),
    "copy.retry.open.favorable_limit_points.gold": ("open", "favorable_limit_points", "gold"),
    "copy.retry.open.favorable_limit_points.default": ("open", "favorable_limit_points", "default"),
    "copy.retry.close.max_attempts": ("close", "max_attempts"),
    "copy.retry.close.retry_window_seconds": ("close", "retry_window_seconds"),
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


def _coerce_positive_int(value: Any) -> Optional[int]:
    """Validate value is coercible to a non-negative int. Returns None if invalid."""
    try:
        if isinstance(value, bool):  # bool is subclass of int — reject
            return None
        if isinstance(value, (int, float)):
            iv = int(value)
        elif isinstance(value, str):
            iv = int(value.strip())
        else:
            return None
        if iv < 0:
            return None
        return iv
    except Exception:
        return None


def _load_overrides_raw_from_db() -> Any:
    """Best-effort read of system_settings.recovery_overrides. Never raises."""
    try:
        from sqlalchemy import create_engine, text
        from engine.config import get_engine_settings

        settings = get_engine_settings()
        eng = create_engine(settings.DATABASE_URL_SYNC, pool_pre_ping=True, pool_size=1, max_overflow=0)
        with eng.connect() as conn:
            row = conn.execute(
                text("SELECT recovery_overrides FROM system_settings LIMIT 1")
            ).fetchone()
        if row is None:
            return None
        return row[0]
    except Exception as e:
        logger.debug(f"recovery_overrides DB read skipped: {e}")
        return None


def _get_nested(d: dict, path: tuple[str, ...]) -> Any:
    cur: Any = d
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur


def _normalize_overrides(raw: Any) -> dict[tuple[str, ...], int]:
    """Validate and normalize raw overrides into a {path: int} dict.

    Accepts both nested canonical schema and legacy flat (dotted) keys.
    Invalid entries are skipped with a warning. Never raises.
    """
    normalized: dict[tuple[str, ...], int] = {}

    if raw is None:
        return normalized
    if not isinstance(raw, dict):
        logger.warning(
            f"recovery_overrides has unexpected type {type(raw).__name__}; using defaults"
        )
        return normalized

    invalid_keys: list[str] = []

    # 1) Canonical nested schema
    for path in _DEFAULTS.keys():
        val = _get_nested(raw, path)
        if val is None:
            continue
        coerced = _coerce_positive_int(val)
        if coerced is None:
            invalid_keys.append(".".join(path))
            continue
        normalized[path] = coerced

    # 2) Legacy flat keys (only fill paths not already set by nested schema)
    for flat_key, path in _LEGACY_FLAT_MAP.items():
        if path in normalized:
            continue
        if flat_key not in raw:
            continue
        val = raw.get(flat_key)
        if val is None:
            continue
        coerced = _coerce_positive_int(val)
        if coerced is None:
            invalid_keys.append(flat_key)
            continue
        normalized[path] = coerced

    if invalid_keys:
        logger.warning(
            f"recovery_overrides ignored invalid keys: {invalid_keys}; falling back to defaults"
        )

    return normalized


def _build_config(overrides: dict[tuple[str, ...], int]) -> RecoveryConfig:
    def _get(path: tuple[str, ...]) -> int:
        return overrides.get(path, _DEFAULTS[path])

    return RecoveryConfig(
        max_retry_attempts_open=_get(("open", "max_attempts")),
        retry_window_seconds_open=_get(("open", "retry_window_seconds")),
        favorable_limit_points_forex=_get(("open", "favorable_limit_points", "forex")),
        favorable_limit_points_gold=_get(("open", "favorable_limit_points", "gold")),
        favorable_limit_points_default=_get(("open", "favorable_limit_points", "default")),
        max_retry_attempts_close=_get(("close", "max_attempts")),
        retry_window_seconds_close=_get(("close", "retry_window_seconds")),
    )


def get_recovery_config(force_refresh: bool = False) -> RecoveryConfig:
    """Return current effective config, refreshing from DB at most every TTL seconds.

    Safe to call from the recovery worker on every event — DB hits are throttled
    by the in-process TTL cache.
    """
    global _cached_cfg, _cached_at
    now = time.time()
    with _lock:
        if (
            not force_refresh
            and _cached_cfg is not None
            and (now - _cached_at) < _CACHE_TTL_S
        ):
            return _cached_cfg
        try:
            raw = _load_overrides_raw_from_db()
            overrides = _normalize_overrides(raw)
            _cached_cfg = _build_config(overrides)
        except Exception as e:
            # Last-resort guard: never let config loading break the worker.
            logger.warning(f"recovery_config build failed, using hardcoded defaults: {e}")
            _cached_cfg = _build_config({})
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
