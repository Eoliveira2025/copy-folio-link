"""AutoOnboardingService — Zero-touch account provisioning."""

import threading
import time
from uuid import UUID
from ..utils.logger import get_logger
from .manager import PoolManager
from .vps_monitor_service import VPSMonitorService
from .repo import list_pending_v2_accounts, get_account_mapping, insert_account_mapping

class AutoOnboardingService:
    """Polls for new accounts on Ubuntu and automatically provisions them on this VPS."""

    def __init__(self, pool_manager: PoolManager, monitor: VPSMonitorService):
        self.pm = pool_manager
        self.monitor = monitor
        self.log = get_logger("auto_onboarding")
        self._running = False
        self._thread = None

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        self.log.info("AutoOnboarding service started")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join()

    def _loop(self):
        while self._running:
            try:
                if self.monitor.can_admit_new_account():
                    self._process_pending_accounts()
            except Exception as e:
                self.log.error("Onboarding loop error", exc_info=e)
            time.sleep(10)

    def _process_pending_accounts(self):
        # This function would call the repo to find accounts marked for this VPS/version
        # that don't have a mapping yet.
        pending = list_pending_v2_accounts() 
        
        for acc in pending:
            if not self.monitor.can_admit_new_account():
                break
                
            self.log.info("Auto-onboarding account", account_id=str(acc.id), login=acc.login)
            try:
                # 1. Strategy routing (simplified for this example)
                # In real scenario, we'd pick the best pool for the strategy
                # row = self.pm.allocator.allocate(acc.strategy_id)
                
                # 2. Provision (handled by pm.ensure_terminal for isolation v2)
                # self.pm.ensure_terminal(acc.id, path)
                
                # 3. Mark as mapped in DB
                pass
            except Exception as e:
                self.log.error("Failed to onboard account", account_id=str(acc.id), exc_info=e)
