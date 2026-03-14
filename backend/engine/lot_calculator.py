"""
Lot size calculator with strategy-specific copy rules.

COPY RULES:
  - Strategies low, medium, high, pro, expert → EXACT copy (same volume as master)
  - Strategy expert_pro → PROPORTIONAL copy:
      volume = (client_balance / master_balance) * master_volume * risk_multiplier
      Snapped to lot_step and clamped to [min_lot, max_lot]
"""

from __future__ import annotations
import math
from engine.config import get_engine_settings

settings = get_engine_settings()

# Only expert_pro uses proportional calculation
PROPORTIONAL_STRATEGIES = {"expert_pro"}


def calculate_lot_size(
    master_volume: float,
    master_balance: float,
    client_balance: float,
    strategy_level: str = "medium",
    risk_multiplier: float = 1.0,
    min_lot: float = settings.MIN_LOT,
    max_lot: float = settings.MAX_LOT,
    lot_step: float = settings.LOT_STEP,
) -> float:
    """
    Calculate the lot size for a copy trade.

    For most strategies: returns master_volume exactly (1:1 copy).
    For expert_pro: proportional calculation based on balance ratio.

    Returns 0.0 if the calculated volume is below min_lot.
    """
    if master_volume <= 0:
        return 0.0

    # ── EXACT COPY for all strategies except expert_pro ──
    if strategy_level not in PROPORTIONAL_STRATEGIES:
        return min(master_volume, max_lot)

    # ── PROPORTIONAL COPY for expert_pro ──
    if master_balance <= 0 or client_balance <= 0:
        return 0.0

    raw = (client_balance / master_balance) * master_volume * risk_multiplier

    # Snap down to nearest lot_step (e.g., 0.01)
    steps = math.floor(raw / lot_step)
    snapped = round(steps * lot_step, 8)

    if snapped < min_lot:
        return 0.0  # Too small to trade

    return min(snapped, max_lot)
