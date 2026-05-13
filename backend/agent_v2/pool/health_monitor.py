"""HealthMonitor — Global watchdog for terminals and sessions."""

import threading
import time
from typing import Dict, List, Callable
from uuid import UUID

from ..utils.logger import get_logger
from ..config import get_v2_settings

class HealthMonitor:
    """Monitors performance and health of all terminals and sessions."""

    def __init__(self, 
                 get_terminals: Callable[[], List[object]], 
                 get_sessions: Callable[[UUID], List[object]]):
        self._get_terminals = get_terminals
        self._get_sessions = get_sessions
        self._stop_event = threading.Event()
        self._thread = None
        self.settings = get_v2_settings()
        self.log = get_logger("health_monitor")
        self._metrics = {
            "status": "STARTING",
            "terminal_count": 0,
            "resource_status": {"ram_usage_mb": 0, "cpu_usage_pct": 0},
            "performance": {
                "avg_latency_ms": 0,
                "reconnects_count": 0,
                "orders_throughput": 0,
                "stability_score": 100.0,
                "terminals_recycled": 0
            }
        }

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
                self._update_global_metrics()
            except Exception as e:
                self.log.error("health check loop failed", exc_info=e)
            
            interval = getattr(self.settings, "HEALTH_CHECK_INTERVAL_S", 15)
            time.sleep(interval)

    def _check_health(self):
        terminals = self._get_terminals()
        try:
            import psutil
        except ImportError:
            psutil = None

        for t in terminals:
            # 1. Check process liveness
            if not t.is_alive():
                self.log.warning("terminal process dead, restarting", extra={"terminal_id": str(t.terminal_id)})
                t.start()
                continue
            
            # 2. Check for "frozen" MT5 (High CPU for too long or no response)
            if psutil and t._process:
                try:
                    proc = psutil.Process(t._process.pid)
                    cpu = proc.cpu_percent(interval=0.1)
                    mem = proc.memory_info().rss / (1024 * 1024)
                    
                    if cpu > 95.0: # Potential freeze/loop
                        # In a real system, we'd track this over multiple checks
                        # For now, log it
                        self.log.warning("high cpu detected in terminal", extra={"pid": t._process.pid, "cpu": cpu})
                    
                    if mem > 800: # MT5 leaking?
                        self.log.warning("high memory detected in terminal, recycling", extra={"pid": t._process.pid, "ram_mb": mem})
                        t.recycle()
                        self._metrics["performance"]["terminals_recycled"] += 1

                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

    def _update_global_metrics(self):
        terminals = self._get_terminals()
        try:
            import psutil
            cpu = psutil.cpu_percent()
            ram = psutil.virtual_memory().percent
            ram_mb = psutil.virtual_memory().used / (1024 * 1024)
            
            self._metrics["resource_status"] = {
                "ram_usage_mb": ram_mb,
                "ram_usage_pct": ram,
                "cpu_usage_pct": cpu
            }
        except ImportError:
            pass

        self._metrics["terminal_count"] = len(terminals)
        self._metrics["status"] = "HEALTHY" if self._metrics["resource_status"]["cpu_usage_pct"] < 80 else "WARNING"
        
        # Stability score calculation (simplified)
        reconnects = self._metrics["performance"]["reconnects_count"]
        recycled = self._metrics["performance"]["terminals_recycled"]
        score = 100.0 - (reconnects * 2) - (recycled * 5)
        self._metrics["performance"]["stability_score"] = max(0.0, score)

    def get_global_metrics(self) -> Dict:
        return self._metrics

