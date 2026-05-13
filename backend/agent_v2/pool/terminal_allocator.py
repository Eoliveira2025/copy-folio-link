"""TerminalAllocator V2 — Advanced allocation logic for institutional gateway."""

import threading
from typing import Optional, Dict
from uuid import UUID

from ..config import get_v2_settings
from ..utils.logger import get_logger
from . import repo

class TerminalAllocatorV2:
    """Manages allocation of accounts across isolated PooledTerminalProcesses.
    
    Institutional Architecture:
    - 1 Account per Terminal/Process.
    - Terminals are grouped by strategy_id.
    - Capacity is strictly enforced (1:1).
    """

    def __init__(self):
        self.settings = get_v2_settings()
        self.log = get_logger("allocator_v2")
        self._lock = threading.RLock()

    def pick_terminal(self, strategy_id: UUID, master_id: UUID) -> Optional[UUID]:
        """Select an available terminal for a new account.
        
        Selection criteria:
        1. Look for ACTIVE pools (terminals) for this strategy/master with current_load < capacity (1).
        2. If none, look for STANDBY to promote.
        3. Else return None (manager should provision new if allowed).
        """
        with self._lock:
            pools = repo.list_pools_for_strategy(strategy_id)
            for p in pools:
                if p.master_id == master_id and p.status == "ACTIVE":
                    if p.current_load < p.capacity:
                        return p.id
            
            for p in pools:
                if p.master_id == master_id and p.status == "STANDBY":
                    repo.update_pool_status(p.id, "ACTIVE")
                    return p.id

            return None

    def assign(self, account_id: UUID, master_id: UUID, strategy_id: UUID) -> Optional[UUID]:
        """Assign an account to a dedicated terminal and persist mapping."""
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
            self.log.info("account allocated to dedicated terminal", 
                          extra={"account_id": str(account_id), "terminal_id": str(terminal_id)})
            return terminal_id

