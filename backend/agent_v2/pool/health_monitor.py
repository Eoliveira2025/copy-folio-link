"""HealthMonitor — Global watchdog for terminals and sessions."""

import threading
import time
from typing import Dict, List, Callable
from uuid import UUID

from ..utils.logger import get_logger
from ..config import get_v2_settings

class HealthMonitor:
    """Monitors performance and health of all terminals and sessions.
    
    Responsibilities:
    - Track CPU/RAM usage per terminal process.
    - Monitor session connectivity.
    - Trigger restarts or rebalancing.
    """

    def __init__(self, 
                 get_terminals: Callable[[], List[object]], 
                 get_sessions: Callable[[UUID], List[object]]):
        self._get_terminals = get_terminals
        self._get_sessions = get_sessions
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.settings = get_v2_settings()
        self.log = get_logger("health_monitor")

    def start(self):
        if self._thread: return
        self._thread = threading.Thread(target=self._run, daemon=True, name="v2-health-monitor")
        self._thread.start()
        self.log.info("health monitor started")

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join()

    def _run(self):
        while not self._stop_event.is_set():
            try:
                self._check_health()
            except Exception as e:
                self.log.error("health check loop failed", exc_info=e)
            
            # Use settings or default 15s
            interval = getattr(self.settings, "HEALTH_CHECK_INTERVAL_S", 15)
            time.sleep(interval)

    def _check_health(self):
        terminals = self._get_terminals()
        for t in terminals:
            # Check process liveness
            if not t.is_alive():
                self.log.warning("terminal process dead, restarting", extra={"terminal_id": str(t.terminal_id)})
                t.start()
                continue
            
            # Check sessions within terminal
            sessions = self._get_sessions(t.terminal_id)
            for s in sessions:
                if not s.is_logged_in and s.should_retry_login():
                    self.log.info("triggering session reconnect", 
                                  account_id=str(s.account_id), login=s.login)
                    # The actual login is handled by the AccountSession logic when a task arrives,
                    # or we could trigger an explicit login task here.

    def get_global_metrics(self) -> Dict:
        # Placeholder for aggregated metrics
        return {
            "terminal_count": len(self._get_terminals()),
            "status": "healthy"
        }
