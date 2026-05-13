"""Smoke test for Institutional Multi-Account V2 architecture."""

import os
import uuid
import time
from agent_v2.pool.manager import PoolManager
from agent_v2.config import get_v2_settings

def run_test():
    print("Starting Institutional V2 Smoke Test...")
    
    # Enable feature flag for test
    os.environ["V2_MT5_POOL_V2_ENABLED"] = "true"
    get_v2_settings.cache_clear()
    
    manager = PoolManager()
    manager.start()
    
    # 1. Simulate Terminal Provisioning
    tid1 = uuid.uuid4()
    tpath1 = r"C:\MT5_Pool_V2\smoke_inst_01"
    
    print(f"Provisioning terminal {tid1}...")
    # In smoke test, terminal start will likely fail FS check on non-Windows, 
    # but the logic should hold.
    t1 = manager.ensure_terminal(tid1, tpath1)
    
    # 2. Register multiple accounts to the same terminal
    acc1 = uuid.uuid4()
    acc2 = uuid.uuid4()
    
    print(f"Registering accounts to terminal {tid1}...")
    manager.register_account(acc1, tid1, 10001, "Exness-Trial")
    manager.register_account(acc2, tid1, 10002, "Exness-Trial2")
    
    sm = manager.get_session_manager(tid1)
    if sm:
        print(f"Sessions in terminal {tid1}: {sm.get_active_count()}")
        assert sm.get_active_count() == 2
    
    # 3. Check Health Monitor
    metrics = manager.health.get_global_metrics()
    print(f"Global metrics: {metrics}")
    assert metrics["terminal_count"] == 1
    
    # 4. Cleanup
    manager.stop()
    print("Test Complete: Institutional V2 structure is valid.")

if __name__ == "__main__":
    run_test()
