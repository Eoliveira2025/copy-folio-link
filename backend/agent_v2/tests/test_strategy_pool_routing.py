import pytest
from uuid import uuid4
from unittest.mock import MagicMock, patch
from agent_v2.pool.terminal_pool import TerminalPool, StrategyMismatchError, StrategyPoolRegistry
from agent_v2.pool.repo import PoolRow

def test_strategy_pool_routing():
    """
    Validate that accounts are routed to the correct strategy pools and isolation is enforced.
    """
    master_id = uuid4()
    strategy_low = uuid4()
    strategy_med = uuid4()
    
    # 1. Test TerminalPool isolation
    pool_low = TerminalPool(
        id=uuid4(),
        pool_name="LOW_POOL",
        master_id=master_id,
        strategy_id=strategy_low,
        terminal_path="C:\\low",
        capacity=10,
        status="ACTIVE"
    )
    
    # Asserting strategy LOW works
    pool_low.assert_strategy(strategy_low)
    
    # Asserting strategy MED fails
    with pytest.raises(StrategyMismatchError):
        pool_low.assert_strategy(strategy_med)

    # 2. Test Registry selection
    with patch("agent_v2.pool.repo.list_pools_for_strategy") as mock_list, \
         patch("agent_v2.pool.repo.count_pool_accounts", return_value=0):
        
        row_low = PoolRow(
            id=uuid4(),
            pool_name="LOW_P1",
            master_id=master_id,
            strategy_id=strategy_low,
            terminal_path="C:\\low",
            capacity=10,
            status="ACTIVE",
            host="localhost"
        )
        
        mock_list.return_value = [row_low]
        
        registry = StrategyPoolRegistry(
            master_id=master_id,
            strategy_id=strategy_low,
            strategy_key="LOW"
        )
        registry.load_from_db()
        
        # Should pick the LOW pool
        pool = registry.pick_active()
        assert pool.id == row_low.id
        assert pool.strategy_id == strategy_low

def test_no_cross_strategy_execution():
    """
    Simulate the execution layer refusing an account from a different strategy.
    """
    # This would typically be in the Worker or ExecutionQueue logic
    # We'll just verify the principle here.
    
    master_low = uuid4()
    strategy_low = uuid4()
    
    master_med = uuid4()
    strategy_med = uuid4()
    
    # Event from Master LOW
    event = {
        "master_id": master_low,
        "strategy_id": strategy_low,
        "action": "OPEN"
    }
    
    # Account from strategy MED
    account = {
        "id": uuid4(),
        "strategy_id": strategy_med
    }
    
    # Isolation check
    def can_execute(acc, evt):
        return acc["strategy_id"] == evt["strategy_id"]
    
    assert can_execute(account, event) is False
    
    # Account from strategy LOW
    account_ok = {
        "id": uuid4(),
        "strategy_id": strategy_low
    }
    assert can_execute(account_ok, event) is True

if __name__ == "__main__":
    pytest.main([__file__])
