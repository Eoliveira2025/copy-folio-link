"""Institutional V2 Simulation Test."""

import unittest
from uuid import uuid4
from unittest.mock import MagicMock
import sys

# Mock dependencies before importing our modules
sys.modules['cryptography'] = MagicMock()
sys.modules['cryptography.fernet'] = MagicMock()
sys.modules['MetaTrader5'] = MagicMock()
sys.modules['psycopg2'] = MagicMock()

from backend.agent_v2.pool.strategy_router import StrategyRouter
from backend.agent_v2.pool.terminal_process import PooledTerminalProcess
from backend.agent_v2.pool.account_session import AccountSession
from backend.agent_v2.exec.order_task import OrderTask, OrderAction

class TestInstitutionalV2(unittest.TestCase):

    def setUp(self):
        self.manager = MagicMock()
        self.mock_repo = MagicMock()
        self.router = StrategyRouter(self.manager, repo_module=self.mock_repo)
        
        self.low_strategy = uuid4()
        self.medium_strategy = uuid4()
        
        self.account_low = uuid4()
        self.account_medium = uuid4()
        self.master_id = uuid4()
        self.pool_id = uuid4()
        self.terminal_id = uuid4()

    def test_strategy_isolation(self):
        """Test that LOW client cannot receive MEDIUM order."""
        mapping = MagicMock()
        mapping.strategy_id = self.low_strategy
        mapping.terminal_id = self.terminal_id
        self.mock_repo.get_account_mapping.return_value = mapping
        
        task = OrderTask(
            account_id=self.account_low,
            pool_id=self.pool_id,
            terminal_id=self.terminal_id,
            master_id=self.master_id,
            strategy_id=self.low_strategy,
            action=OrderAction.OPEN,
            symbol="EURUSD",
            volume=0.01,
            master_ticket=123
        )
        
        result = self.router.route_and_execute(task, master_strategy_id=self.medium_strategy)
        self.assertFalse(result, "Order should be blocked due to strategy mismatch")

    def test_routing_success(self):
        """Test that order is routed when strategy matches."""
        mapping = MagicMock()
        mapping.strategy_id = self.low_strategy
        mapping.terminal_id = self.terminal_id
        self.mock_repo.get_account_mapping.return_value = mapping
        
        details = MagicMock()
        details.login = 12345
        self.mock_repo.get_account_details.return_value = details
        
        terminal = MagicMock()
        terminal.is_alive.return_value = True
        self.manager.get_terminal.return_value = terminal
        
        session = MagicMock()
        session.acquire.return_value.__enter__.return_value = {}
        self.manager.get_session.return_value = session
        
        task = OrderTask(
            account_id=self.account_low,
            pool_id=self.pool_id,
            terminal_id=self.terminal_id,
            master_id=self.master_id,
            strategy_id=self.low_strategy,
            action=OrderAction.OPEN,
            symbol="EURUSD",
            volume=0.01,
            master_ticket=123
        )
        
        result = self.router.route_and_execute(task, master_strategy_id=self.low_strategy)
        self.assertTrue(result, "Order should be routed successfully")

if __name__ == "__main__":
    unittest.main()
