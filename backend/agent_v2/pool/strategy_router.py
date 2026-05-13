"""Institutional Strategy Router — Rotes orders to correct execution pools."""

from typing import Dict, Optional, List
from uuid import UUID
from backend.agent_v2.exec.order_task import OrderTask, TaskStatus
from backend.agent_v2.utils.logger import get_logger

class StrategyRouter:
    """Routes execution tasks to the correct terminal based on strategy isolation."""

    def __init__(self, pool_manager, repo_module=None):
        self.pool_manager = pool_manager
        if repo_module is None:
            from . import repo
            self.repo = repo
        else:
            self.repo = repo_module
        self.log = get_logger("strategy_router")

    def route_and_execute(self, task: OrderTask, master_strategy_id: UUID) -> bool:
        """Validates strategy and routes to account's dedicated terminal."""
        account_id = task.account_id
        log = self.log.bind(account_id=str(account_id), master_strategy_id=str(master_strategy_id))

        # 1. Get account mapping
        mapping = self.repo.get_account_mapping(account_id)
        if not mapping:
            log.error("account not mapped to any terminal")
            return False

        # 2. Institutional Safety: strategy isolation
        if mapping.strategy_id != master_strategy_id:
            log.critical("STRATEGY MISMATCH DETECTED - EXECUTION BLOCKED", 
                         extra={"account_strategy": str(mapping.strategy_id)})
            return False

        # 3. Validation
        details = self.repo.get_account_details(account_id)
        if not details:
            log.error("account details not found")
            return False

        # 4. Get terminal and session
        terminal = self.pool_manager.get_terminal(mapping.terminal_id)
        session = self.pool_manager.get_session(mapping.terminal_id)

        if not terminal or not session:
            log.error("terminal or session not initialized")
            return False

        if not terminal.is_alive():
            log.warning("terminal dead, attempting restart")
            terminal.start()

        # 5. Execute via session (1:1 isolation)
        try:
            with session.acquire(account_id=account_id, login=details.login) as session_info:
                # Execution logic would go here, calling MT5 bridge
                log.info("executing order on dedicated terminal", extra={"terminal_id": str(mapping.terminal_id)})
                # Placeholder for real order_send
                return True
        except Exception as e:
            log.error("execution failed", exc_info=e)
            return False

