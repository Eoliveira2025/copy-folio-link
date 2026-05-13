"""Trading utilities for V2: Volume scaling and Symbol mapping.
"""

from __future__ import annotations
from typing import Optional
from uuid import UUID
from .logger import get_logger

log = get_logger("trading_utils")

class VolumeCalculator:
    """Calculates client volume based on master volume and balance ratio."""
    
    @staticmethod
    def calculate(
        master_volume: float,
        master_balance: float,
        client_balance: float,
        min_lot: float = 0.01,
        max_lot: float = 100.0,
        lot_step: float = 0.01
    ) -> float:
        if master_balance <= 0 or client_balance <= 0:
            return master_volume # Fallback
            
        ratio = client_balance / master_balance
        raw_vol = master_volume * ratio
        
        # Round to step
        import math
        steps = round(raw_vol / lot_step)
        vol = steps * lot_step
        
        # Clamp
        vol = max(min_lot, min(max_lot, vol))
        return round(vol, 2)

class SymbolMapper:
    """Maps symbols between different broker naming conventions (e.g. Exness 'm' suffix)."""
    
    def __init__(self, mapping: Optional[dict[str, str]] = None, default_suffix: str = ""):
        self.mapping = mapping or {}
        self.default_suffix = default_suffix

    def map(self, symbol: str) -> str:
        # 1. Explicit mapping
        if symbol in self.mapping:
            return self.mapping[symbol]
            
        # 2. Suffix rule
        if self.default_suffix and not symbol.endswith(self.default_suffix):
            return f"{symbol}{self.default_suffix}"
            
        return symbol

def get_master_stats(master_id: UUID) -> dict:
    """Helper to fetch master stats from Redis."""
    from ..redis_client import get_redis, k
    try:
        r = get_redis()
        data = r.hgetall(k(f"master:{master_id}:stats"))
        if not data:
            return {}
        return {
            "balance": float(data.get(b"balance", 0.0)),
            "equity": float(data.get(b"equity", 0.0))
        }
    except Exception:
        return {}

def get_client_stats(account_id: UUID) -> dict:
    """Placeholder: in production this might fetch from DB or recent heartbeat."""
    # For V2, we might need a separate service that polls client balances.
    # For now, we'll return a default or use DB value if available.
    return {"balance": 1000.0} # TODO: Real balance fetch
