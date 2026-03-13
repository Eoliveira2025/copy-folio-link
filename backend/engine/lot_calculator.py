"""Proportional lot size calculator with risk multipliers and symbol constraints."""

from __future__ import annotations
import math
from engine.config import get_engine_settings

settings = get_engine_settings()

# Strategy risk multipliers — adjust copied volume
STRATEGY_MULTIPLIERS: dict[str, float] = {
    "low": 0.5,
    "medium": 1.0,
    "high": 1.5,
    "pro": 2.0,
    "expert": 2.5,
    "expert_pro": 3.0,
}


def calculate_lot_size(
    master_volume: float,
    master_balance: float,
    client_balance: float,
    strategy_level: str = "medium",
    min_lot: float = settings.MIN_LOT,
    max_lot: float = settings.MAX_LOT,
    lot_step: float = settings.LOT_STEP,
) -> float:
    """
    Proportional lot calculation:
      client_lots = master_lots × (client_balance / master_balance) × strategy_multiplier

    Then snapped to lot_step and clamped to [min_lot, max_lot].
    Returns 0.0 if client balance is too small for min_lot.
    """
    if master_balance <= 0 or client_balance <= 0:
        return 0.0

    multiplier = STRATEGY_MULTIPLIERS.get(strategy_level, 1.0)
    raw = master_volume * (client_balance / master_balance) * multiplier

    # Snap down to nearest lot_step
    steps = math.floor(raw / lot_step)
    snapped = round(steps * lot_step, 8)

    if snapped < min_lot:
        return 0.0  # Too small to trade

    return min(snapped, max_lot)
