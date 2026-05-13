"""ResourceGuard — Protection for VPS resource limits."""

from __future__ import annotations
import os
import threading
import time
from typing import Dict
from ..config import get_v2_settings
from ..utils.logger import get_logger

try:
    import psutil
except ImportError:
    psutil = None

class ResourceGuard:
    """Monitors VPS resources and enforces safety limits."""

    def __init__(self):
        self.settings = get_v2_settings()
        self.log = get_logger("resource_guard")
        self._lock = threading.Lock()
        self._last_check = 0.0
        self._status = {"safe": True, "reason": None}

    def check_resources(self) -> bool:
        """Returns True if resources are within safe limits."""
        if not self.settings.V2_RESOURCE_GUARD_ENABLED:
            return True

        now = time.time()
        if now - self._last_check < 5.0:
            return self._status["safe"]

        self._last_check = now
        
        if psutil is None:
            return True

        try:
            cpu_usage = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory()
            ram_usage = ram.percent

            with self._lock:
                if cpu_usage > self.settings.MAX_CPU_USAGE_PCT:
                    self._status = {"safe": False, "reason": f"CPU too high: {cpu_usage}%"}
                    self.log.warning("VPS OVERLOADED: CPU", extra={"cpu": cpu_usage})
                elif ram_usage > 90.0: # Hard ram limit
                    self._status = {"safe": False, "reason": f"RAM too high: {ram_usage}%"}
                    self.log.warning("VPS OVERLOADED: RAM", extra={"ram": ram_usage})
                else:
                    self._status = {"safe": True, "reason": None}
            
            return self._status["safe"]
        except Exception as e:
            self.log.error("resource check failed", exc_info=e)
            return True

    def get_status(self) -> Dict:
        with self._lock:
            return dict(self._status)
