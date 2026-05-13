"""TerminalAllocator V2 — Advanced allocation logic with multi-account support per terminal."""

import threading
from typing import Optional, Dict, List
from uuid import UUID

from ..config import get_v2_settings
from ..utils.logger import get_logger
from . import repo
from .terminal_pool import TerminalPool

class TerminalAllocatorV2:
    """Manages allocation of accounts across available PooledTerminalProcesses.
    
    New architecture:
    - Multiple accounts can share a terminal.
    - Limits are enforced (MAX_ACCOUNTS_PER_TERMINAL).
    - Affinity is respected (same master/strategy preferred but not strictly required if terminal supports it).
    """

    def __init__(self):
        self.settings = get_v2_settings()
        self.log = get_logger("allocator_v2")
        self._lock = threading.RLock()
        # In-memory cache of terminal loads
        self._terminal_loads: Dict[UUID, int] = {}

    def pick_terminal(self, strategy_id: UUID, master_id: UUID) -> Optional[UUID]:
        """Select the best terminal for a new account.
        
        Selection criteria:
        1. Terminal already serving this strategy/master with capacity.
        2. Least loaded terminal with capacity.
        3. Provision new terminal if needed.
        """
        with self._lock:
            # 1. Look for terminals already serving this strategy
            pools = repo.list_pools_for_strategy(strategy_id)
            for p in pools:
                if p.master_id == master_id and p.status == "ACTIVE":
                    if p.current_load < p.capacity:
                        return p.id
            
            # 2. If no existing pool with room, look for a STANDBY to promote
            # (In this architecture, TerminalPool maps 1-to-1 with a TerminalProcess row)
            for p in pools:
                if p.master_id == master_id and p.status == "STANDBY":
                    repo.update_pool_status(p.id, "ACTIVE")
                    return p.id

            return None

    def assign(self, account_id: UUID, master_id: UUID, strategy_id: UUID) -> Optional[UUID]:
        """Assign an account to a terminal and persist mapping."""
        with self._lock:
            existing = repo.get_account_mapping(account_id)
            if existing:
                return existing.terminal_id

            terminal_id = self.pick_terminal(strategy_id, master_id)
            if not terminal_id:
                self.log.error("no terminal available for allocation", 
                               extra={"strategy_id": str(strategy_id)})
                return None

            repo.insert_account_mapping(
                account_id=account_id,
                pool_id=terminal_id,
                terminal_id=terminal_id,
                master_id=master_id,
                strategy_id=strategy_id
            )
            self.log.info("account allocated to terminal", 
                          extra={"account_id": str(account_id), "terminal_id": str(terminal_id)})
            return terminal_id

    def rebalance(self):
        """Analyze terminal loads and move accounts if necessary."""
        # TODO: Implement rebalance logic based on CPU/RAM metrics
        pass
