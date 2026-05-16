"""Resolve broker-specific symbol variants (XAUUSD, XAUUSDm, GOLD...)."""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

from app.utils.logger import get_logger

log = get_logger("mt5.symbol")

# Common suffixes / prefixes used by brokers
SUFFIXES = ["", "m", "z", ".pro", "-ECN", ".r", ".raw", "_i", ".i", "c", "."]
ALIASES = {
    "XAUUSD": ["GOLD", "XAU/USD", "XAUUSD."],
    "XAGUSD": ["SILVER"],
    "BTCUSD": ["BITCOIN"],
}


def _candidates(symbol: str) -> list[str]:
    base = symbol.upper().strip()
    out: list[str] = []
    out.append(base)
    for suf in SUFFIXES:
        if suf and not base.endswith(suf):
            out.append(base + suf)
    for alias in ALIASES.get(base, []):
        out.append(alias)
        for suf in SUFFIXES:
            if suf:
                out.append(alias + suf)
    seen, uniq = set(), []
    for s in out:
        if s not in seen:
            seen.add(s)
            uniq.append(s)
    return uniq


@lru_cache(maxsize=1024)
def resolve(symbol: str) -> Optional[str]:
    """Return the actual symbol name available in the terminal, or None."""
    try:
        import MetaTrader5 as mt5  # type: ignore
    except Exception:
        return None

    all_syms = mt5.symbols_get() or []
    available = {s.name.upper(): s.name for s in all_syms}

    for cand in _candidates(symbol):
        actual = available.get(cand.upper())
        if actual:
            if not mt5.symbol_select(actual, True):
                continue
            log.info("resolved symbol %s -> %s", symbol, actual)
            return actual
    log.warning("symbol %s not found in terminal", symbol)
    return None


def normalize_lot(symbol: str, lot: float) -> Optional[float]:
    """Clamp lot to symbol step / min / max."""
    try:
        import MetaTrader5 as mt5  # type: ignore
    except Exception:
        return lot

    info = mt5.symbol_info(symbol)
    if info is None:
        return None
    step = info.volume_step or 0.01
    vmin = info.volume_min or 0.01
    vmax = info.volume_max or 100.0
    # round down to step
    steps = max(1, int(lot / step))
    norm = round(steps * step, 8)
    if norm < vmin:
        norm = vmin
    if norm > vmax:
        norm = vmax
    return norm
