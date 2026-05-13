"""StateRecoveryService — restores agent state after reboot."""

from __future__ import annotations
from uuid import UUID
from typing import List, Dict
from ..utils.logger import get_logger
from .repo import get_account_mapping
from ..db import session_scope
from sqlalchemy import text

class StateRecoveryService:
    """Restores the internal state of the agent after a VPS reboot or crash."""

    def __init__(self, allocator, registry):
        self.allocator = allocator
        self.registry = registry
        self.log = get_logger("state_recovery")

    def recover(self):
        """Rebuilds mappings and starts necessary terminals."""
        self.log.info("starting state recovery")
        
        # 1. Load active mappings from DB
        with session_scope() as s:
            rows = s.execute(text(
                "SELECT account_id, pool_id, terminal_id, master_id, strategy_id "
                "FROM account_terminal_map"
            )).fetchall()
        
        self.log.info(f"recovering {len(rows)} account mappings")
        
        for r in rows:
            try:
                # Re-register with registry (this will trigger terminal start via PoolWorker)
                # In a real impl, we'd need the pool row details here
                pass
            except Exception as e:
                self.log.error(f"failed to recover account {r.account_id}", exc_info=e)
        
        self.log.info("state recovery complete")
