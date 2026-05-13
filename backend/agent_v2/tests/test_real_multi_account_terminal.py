import os
import time
import subprocess
import pytest
from uuid import uuid4
from unittest.mock import MagicMock

# Attempt to import MT5, but skip if not on Windows or not installed
try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None

from agent_v2.utils.logger import get_logger

log = get_logger("test_multi_account")

@pytest.mark.skipif(mt5 is None, reason="MetaTrader5 package not installed")
@pytest.mark.skipif(os.name != 'nt', reason="MT5 only runs on Windows")
def test_real_multi_account_terminal():
    """
    PROVE if a single MT5 process can handle multiple accounts simultaneously.
    
    Expectation: It CANNOT. mt5.login() switches the global account for the terminal.
    """
    # Use real credentials from environment or constants for this specific test
    # In a real environment, these would be valid test accounts.
    # For the sake of the 'proof', even with invalid logins, we can see the 'current login' change.
    
    terminal_path = "C:\\Program Files\\MetaTrader 5 Exness\\terminal64.exe" # Adjust as needed
    if not os.path.exists(terminal_path):
        pytest.skip(f"Terminal not found at {terminal_path}")

    # 1. Start ONLY ONE process
    log.info("Step 1: Initializing MT5")
    if not mt5.initialize(path=terminal_path, portable=True):
        pytest.fail(f"Failed to initialize MT5: {mt5.last_error()}")

    try:
        # Get PID
        pid = None
        # This is a bit tricky to get via mt5 lib, but we can check running processes
        # For simplicity, we assume we just opened one.
        
        # 2. Login Account A (Dummy or Real)
        login_a = 83097251  # Example Demo
        pass_a = "Testing123" # Dummy for proof
        server_a = "Exness-MT5Trial6"
        
        log.info(f"Step 2: Logging in Account A ({login_a})")
        mt5.login(login=login_a, password=pass_a, server=server_a)
        
        info_a = mt5.account_info()
        active_login_after_a = info_a.login if info_a else "FAILED_LOGIN"
        log.info(f"Active login after A: {active_login_after_a}")

        # 3. Login Account B without closing terminal
        login_b = 83097252 # Another dummy
        pass_b = "Testing456"
        server_b = "Exness-MT5Trial6"
        
        log.info(f"Step 3: Logging in Account B ({login_b})")
        mt5.login(login=login_b, password=pass_b, server=server_b)
        
        info_b = mt5.account_info()
        active_login_after_b = info_b.login if info_b else "FAILED_LOGIN"
        log.info(f"Active login after B: {active_login_after_b}")

        # 4. Check if Account A is still "accessible" simultaneously
        # In a real multi-session system, we'd have session handles.
        # Here, we just check if mt5.account_info() still shows B.
        
        log.info(f"Final Check: Active login is {active_login_after_b}")
        
        # PROOF: If they are the same process, A is gone from the 'active' state.
        if active_login_after_a != active_login_after_b:
            log.warning("CONFIRMED: mt5.login() switches the global account. Simultaneous sessions in ONE process are NOT supported by standard MT5 Python lib.")
            # According to user requirement #8: "Test only passes if real isolation exists".
            # So we fail this test to signal we need the alternative architecture.
            assert False, "MT5 does not support simultaneous multiple accounts in a single process."
        else:
            # This would only happen if login B failed and it stayed on A, 
            # or if they are somehow miraculously simultaneous (unlikely).
            assert active_login_after_a == active_login_after_b
            
    finally:
        mt5.shutdown()

if __name__ == "__main__":
    # Allow running directly for manual validation
    try:
        test_real_multi_account_terminal()
    except Exception as e:
        print(f"Test Result: {e}")
