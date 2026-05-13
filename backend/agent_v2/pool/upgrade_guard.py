"""UpgradeGuard — Prevents illegal strategy switching with open positions."""

from uuid import UUID
from typing import Optional, List, Dict
from dataclasses import dataclass
from ..utils.logger import get_logger
from . import repo
import threading

@dataclass
class UpgradeState:
    account_id: UUID
    old_strategy_id: UUID
    new_strategy_id: UUID
    status: str  # PENDING, RECOVERY, COMPLETED
    open_symbols: List[str]

class UpgradeGuard:
    """Manages strategy upgrades safely.
    
    Rules:
    - If upgrade pending, block new entries of OLD and NEW strategy.
    - Allow only recovery/management of existing positions.
    - Switch to NEW strategy only when ALL old positions are closed.
    """
    
    def __init__(self, repo_module=None):
        self.repo = repo_module or repo
        self.log = get_logger("upgrade_guard")
        self._lock = threading.RLock()

    def check_execution_allowed(self, 
                                account_id: UUID, 
                                strategy_id: UUID, 
                                symbol: str, 
                                is_initial_entry: bool) -> bool:
        """
        Validates if an order can be executed for the given account/strategy/symbol.
        
        Returns:
        - True if allowed.
        - False if blocked by upgrade rules.
        """
        # 1. Check if account is in upgrade transition
        # This would typically read from a `strategy_upgrade_status` table
        # For now, we simulate with a status check in DB
        
        # details = self.repo.get_upgrade_status(account_id)
        # if not details: return True (normal flow)
        
        # Simulate logic:
        # if details.status == 'PENDING':
        #    if is_initial_entry: return False
        #    if symbol in details.open_symbols: return True
        #    return False
        
        return True # Placeholder until DB schema is ready

    def can_switch_strategy(self, account_id: UUID, open_positions_count: int) -> bool:
        """Determines if a strategy switch is safe."""
        return open_positions_count == 0

    def get_account_status(self, account_id: UUID) -> str:
        """Returns the enhanced status for the monitor."""
        # active, upgrade_pending_strategy_switch, recovery_only_old_strategy, etc.
        return "active"
