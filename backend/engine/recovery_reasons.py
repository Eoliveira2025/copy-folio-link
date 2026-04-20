"""Map raw MT5 retcode / error string into standardized reason codes."""

from __future__ import annotations
from typing import Tuple

# MT5 retcodes we care about
MT5_RETCODES = {
    10004: ("requote", "requote"),
    10006: ("requote", "request_rejected"),
    10010: ("requote", "request_only_partial"),
    10013: ("symbol_not_found", "invalid_request"),
    10014: ("volume_invalid", "invalid_volume"),
    10015: ("price_off_quotes", "invalid_price"),
    10016: ("price_off_quotes", "invalid_stops"),
    10017: ("trade_context_busy", "trade_disabled"),
    10018: ("market_closed", "market_closed"),
    10019: ("insufficient_margin", "no_money"),
    10020: ("price_off_quotes", "price_changed"),
    10021: ("price_off_quotes", "price_off"),
    10024: ("trade_context_busy", "too_many_requests"),
    10027: ("trade_context_busy", "autotrading_disabled_client"),
    10028: ("trade_context_busy", "autotrading_disabled_server"),
    10030: ("unsupported_filling_mode", "unsupported_filling"),
}


def classify_mt5_error(retcode: int | None, error_message: str | None) -> Tuple[str, str]:
    """Return (reason_code, retcode_comment)."""
    if retcode is not None and retcode in MT5_RETCODES:
        return MT5_RETCODES[retcode]

    msg = (error_message or "").lower()
    if "no money" in msg or "insufficient" in msg or "margin" in msg:
        return ("insufficient_margin", error_message or "no money")
    if "market closed" in msg or "market is closed" in msg:
        return ("market_closed", error_message or "market closed")
    if "not found" in msg and "symbol" in msg:
        return ("symbol_not_found", error_message or "symbol not found")
    if "volume" in msg and ("invalid" in msg or "minimum" in msg):
        return ("volume_invalid", error_message or "volume invalid")
    if "disconnected" in msg or "no connection" in msg:
        return ("account_disconnected", error_message or "account disconnected")
    if "context busy" in msg or "trade context" in msg:
        return ("trade_context_busy", error_message or "trade context busy")
    if "off quotes" in msg or "price changed" in msg:
        return ("price_off_quotes", error_message or "price off quotes")
    if "requote" in msg:
        return ("requote", error_message or "requote")
    if "filling" in msg:
        return ("unsupported_filling_mode", error_message or "unsupported filling")

    return ("unknown_error", error_message or "unknown error")
