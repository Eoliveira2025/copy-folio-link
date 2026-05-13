"""Test Operational Hardening in Sandbox."""

import time
import uuid
from backend.agent_v2.pool.manager import PoolManager
from backend.agent_v2.config import get_v2_settings
from backend.agent_v2.monitor_app.institutional_ui import InstitutionalMonitorApp
from backend.agent_v2.pool.vps_monitor_service import VPSMonitorService

def test_hardening():
    settings = get_v2_settings()
    settings.V2_AUTO_REMOVE_DISCONNECTED_ACCOUNTS = True
    
    print("--- Starting Hardening Test ---")
    pool = PoolManager()
    pool.start()
    
    vps_monitor = VPSMonitorService()
    ui = InstitutionalMonitorApp(pool, vps_monitor, pool.health)
    
    # 1. Create a dummy terminal
    terminal_id = uuid.uuid4()
    # We use a non-existent path to see how it handles failure
    print(f"Adding test terminal: {terminal_id}")
    pool.ensure_terminal(terminal_id, "C:\\Temp\\MT5_Fake")
    
    time.sleep(2)
    
    # 2. Check UI data
    data = ui.get_dashboard_data()
    print(f"Dashboard status: {data['status']}")
    print(f"Terminals: {data['counts']['terminals']}")
    
    # 3. Test Action: Reconnect
    print("Triggering Reconnect action...")
    res = ui.handle_action("reconnect", str(terminal_id))
    print(f"Action Result: {res}")
    
    # 4. Test Action: Recycle
    print("Triggering Recycle action...")
    res = ui.handle_action("recycle", str(terminal_id))
    print(f"Action Result: {res}")
    
    # 5. Check logs helper
    print(f"Support Tool Simulation: Finding logs for {terminal_id}")
    from backend.agent_v2.tools.support_helper import find_account_logs
    find_account_logs(str(terminal_id))
    
    # 6. Stop
    print("Stopping pool...")
    pool.stop()
    print("Hardening Test Complete.")

if __name__ == "__main__":
    test_hardening()
