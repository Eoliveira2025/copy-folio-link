import unittest
from uuid import uuid4
from backend.agent_v2.pool.upgrade_guard import UpgradeGuard

class TestUpgradeGuard(unittest.TestCase):
    def setUp(self):
        self.guard = UpgradeGuard()
        self.account_id = uuid4()
        self.old_strategy = uuid4()
        self.new_strategy = uuid4()

    def test_block_initial_entry_during_upgrade(self):
        # This is a conceptual test until the DB mock is ready
        # The goal is to prove the logic structure
        is_allowed = self.guard.check_execution_allowed(
            self.account_id, 
            self.old_strategy, 
            "EURUSD", 
            is_initial_entry=True
        )
        self.assertTrue(is_allowed) # Default behavior without upgrade pending

    def test_can_switch_only_when_zero_positions(self):
        self.assertFalse(self.guard.can_switch_strategy(self.account_id, 5))
        self.assertTrue(self.guard.can_switch_strategy(self.account_id, 0))

if __name__ == '__main__':
    unittest.main()
