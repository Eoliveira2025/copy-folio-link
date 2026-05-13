"""Institutional V2 Component Tests."""

import unittest
from uuid import uuid4
from unittest.mock import MagicMock
import sys
import os

# Mock dependencies
sys.modules['cryptography'] = MagicMock()
sys.modules['cryptography.fernet'] = MagicMock()
sys.modules['MetaTrader5'] = MagicMock()
sys.modules['psycopg2'] = MagicMock()

from backend.agent_v2.pool.failover_safe_mode import FailoverSafeMode
from backend.agent_v2.pool.execution_deduplication_service import ExecutionDeduplicationService

class TestInstitutionalComponents(unittest.TestCase):

    def test_safe_mode_logic(self):
        safe_mode = FailoverSafeMode()
        safe_mode.settings.V2_INSTITUTIONAL_SAFE_MODE_ENABLED = True
        
        self.assertFalse(safe_mode.is_active())
        self.assertTrue(safe_mode.can_open())
        
        safe_mode.activate("Test crash")
        
        self.assertTrue(safe_mode.is_active())
        self.assertFalse(safe_mode.can_open())
        self.assertEqual(safe_mode.get_reason(), "Test crash")
        
        safe_mode.deactivate()
        self.assertFalse(safe_mode.is_active())
        self.assertTrue(safe_mode.can_open())

    def test_deduplication(self):
        service = ExecutionDeduplicationService()
        service.settings.V2_EXECUTION_DEDUP_ENABLED = True
        
        aid = uuid4()
        sid = uuid4()
        
        # First execution
        is_dup = service.is_duplicate(aid, 12345, "OPEN", "EURUSD", 0.1, sid)
        self.assertFalse(is_dup)
        
        # Second execution (exact same params)
        is_dup = service.is_duplicate(aid, 12345, "OPEN", "EURUSD", 0.1, sid)
        self.assertTrue(is_dup)
        
        # Different ticket
        is_dup = service.is_duplicate(aid, 12346, "OPEN", "EURUSD", 0.1, sid)
        self.assertFalse(is_dup)

if __name__ == "__main__":
    unittest.main()
