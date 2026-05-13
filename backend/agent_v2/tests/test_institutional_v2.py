"""Institutional V2 Simulation Test."""

import unittest
from uuid import uuid4
from unittest.mock import MagicMock
import sys

# Mock dependencies before importing our modules
sys.modules['cryptography'] = MagicMock()
sys.modules['cryptography.fernet'] = MagicMock()
sys.modules['MetaTrader5'] = MagicMock()

from backend.agent_v2.pool.strategy_router import StrategyRouter
from backend.agent_v2.pool.terminal_process import PooledTerminalProcess
from backend.agent_v2.pool.account_session import AccountSession
from backend.agent_v2.exec.order_task import OrderTask

class TestInstitutionalV2(unittest.TestCase):

    def setUp(self):
        self.manager = MagicMock()
        self.router = StrategyRouter(self.manager)
        
        self.low_strategy = uuid4()
        self.medium_strategy = uuid4()
        
        self.account_low = uuid4()
        self.account_medium = uuid4()

    def test_strategy_isolation(self):
        """Test that LOW client cannot receive MEDIUM order."""
        # 1. Setup mapping mock
        from backend.agent_v2.pool import repo
        repo.get_account_mapping = MagicMock()
        
        # Mapping for LOW account
        low_mapping = MagicMock()
        low_mapping.strategy_id = self.low_strategy
        low_mapping.terminal_id = uuid4()
        
        repo.get_account_mapping.return_value = low_mapping
        
        # 2. Create task for LOW account
        task = OrderTask(
            account_id=self.account_low,
            master_ticket=123,
            symbol="EURUSD",
            action="OPEN",
            volume=0.01
        )
        
        # 3. Attempt to route with MEDIUM strategy
        result = self.router.route_and_execute(task, master_strategy_id=self.medium_strategy)
        
        # 4. Must be blocked
        self.assertFalse(result, "Order should be blocked due to strategy mismatch")

    def test_routing_success(self):
        """Test that order is routed when strategy matches."""
        from backend.agent_v2.pool import repo
        repo.get_account_mapping = MagicMock()
        repo.get_account_details = MagicMock()
        
        mapping = MagicMock()
        mapping.strategy_id = self.low_strategy
        mapping.terminal_id = uuid4()
        repo.get_account_mapping.return_value = mapping
        
        details = MagicMock()
        details.login = 12345
        repo.get_account_details.return_value = details
        
        terminal = MagicMock()
        terminal.is_alive.return_value = True
        self.manager.get_terminal.return_value = terminal
        
        session = MagicMock()
        session.acquire.return_value.__enter__.return_value = {}
        self.manager.get_session.return_value = session
        
        task = OrderTask(
            account_id=self.account_low,
            master_ticket=123,
            symbol="EURUSD",
            action="OPEN",
            volume=0.01
        )
        
        result = self.router.route_and_execute(task, master_strategy_id=self.low_strategy)
        self.assertTrue(result, "Order should be routed successfully")

if __name__ == "__main__":
    unittest.main()
