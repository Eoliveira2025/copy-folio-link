import pytest
import time
from uuid import uuid4
from unittest.mock import MagicMock, patch
from agent_v2.pool.account_session import AccountSession, LoginFailedError
from agent_v2.pool.terminal_process import PooledTerminalProcess

def test_pool_no_infinite_restart():
    """
    Validate that failed credentials do not cause infinite terminal restarts.
    """
    pool_id = uuid4()
    terminal_id = uuid4()
    account_id = uuid4()
    login = 12345
    
    # Mock account details loader
    mock_details = MagicMock()
    mock_details.login = login
    mock_details.encrypted_password = b"fake_enc_pass"
    mock_details.server = "FakeServer"
    
    loader = MagicMock(return_value=mock_details)
    
    # 1. Test AccountSession retry limit
    # We patch _is_dry_run to return False to trigger real-ish logic (which we then mock)
    with patch("agent_v2.pool.account_session._is_dry_run", return_value=False), \
         patch("MetaTrader5.initialize", return_value=True), \
         patch("MetaTrader5.login", return_value=False), \
         patch("MetaTrader5.last_error", return_value=(1, "Invalid credentials")), \
         patch("agent_v2.pool.account_session.decrypt_mt5_password", return_value="plain"):
        
        session = AccountSession(
            pool_id=pool_id,
            terminal_id=terminal_id,
            terminal_path="C:\\fake",
            account_details_loader=loader
        )
        
        # Try login multiple times
        fail_count = 0
        for _ in range(3):
            try:
                with session.acquire(account_id=account_id, login=login):
                    pass
            except LoginFailedError:
                fail_count += 1
        
        assert fail_count == 3
        assert session.login_count() == 3 # It attempted 3 times

    # 2. Test TerminalProcess restart limit
    with patch("subprocess.Popen") as mock_popen:
        mock_popen.return_value.poll.return_value = None # Alive
        
        proc = PooledTerminalProcess(terminal_id=terminal_id, terminal_path="C:\\fake")
        
        # Manually set settings limit for test
        proc.settings.MAX_RESTARTS_PER_HOUR = 2
        
        # First 2 starts should work
        assert proc.start() is True
        proc.stop()
        assert proc.start() is True
        proc.stop()
        
        # 3rd start should fail because of rate limit
        assert proc.start() is False
        assert "max restarts per hour reached" in str(proc.log) # Placeholder check

def test_duplicate_terminal_prevention():
    """
    Validate that we don't create multiple processes for the same terminal_id.
    """
    from agent_v2.pool.manager import PoolManager
    
    manager = PoolManager()
    tid = uuid4()
    path = "C:\\fake"
    
    with patch("agent_v2.pool.terminal_process.PooledTerminalProcess.start") as mock_start, \
         patch("pathlib.Path.exists", return_value=True):
        
        t1 = manager.ensure_terminal(tid, path)
        t2 = manager.ensure_terminal(tid, path)
        
        assert t1 is t2
        assert mock_start.call_count == 1 # Only started once

if __name__ == "__main__":
    pytest.main([__file__])
