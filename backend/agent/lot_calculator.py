"""
Lot size calculator for the Windows VPS Agent.

COPY RULES:
  - Strategies low, medium, high, pro, expert → EXACT copy (1:1 volume)
  - Strategy expert_pro → PROPORTIONAL copy:
      volume = (client_balance / master_balance) * master_volume * risk_multiplier
"""

from __future__ import annotations
import math

PROPORTIONAL_STRATEGIES = {"expert_pro"}


def calculate_lot_size(
    master_volume: float,
    master_balance: float,
    client_balance: float,
    strategy_level: str = "medium",
    risk_multiplier: float = 1.0,
    min_lot: float = 0.01,
    max_lot: float = 100.0,
    lot_step: float = 0.01,
) -> float:
    """
    For most strategies: returns master_volume exactly (1:1 copy).
    For expert_pro: proportional calculation based on balance ratio.
    Returns 0.0 if below min_lot.
    """
    if master_volume <= 0:
        return 0.0

    # EXACT COPY for all strategies except expert_pro
    if strategy_level not in PROPORTIONAL_STRATEGIES:
        return min(master_volume, max_lot)

    # PROPORTIONAL COPY for expert_pro
    if master_balance <= 0 or client_balance <= 0:
        return 0.0

    raw = (client_balance / master_balance) * master_volume * risk_multiplier

    steps = math.floor(raw / lot_step)
    snapped = round(steps * lot_step, 8)

    if snapped < min_lot:
        return 0.0

    return min(snapped, max_lot)
