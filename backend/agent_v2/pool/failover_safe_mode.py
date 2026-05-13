"""FailoverSafeMode — Institutional safety mode."""

from __future__ import annotations
import threading
from typing import Optional
from ..utils.logger import get_logger
from ..config import get_v2_settings

class FailoverSafeMode:
    """Manages institutional safe mode across the agent.
    
    When active:
    - Block new OPEN orders.
    - Only allow CLOSE orders to manage risk.
    - Prevent new account connections.
    """

    def __init__(self):
        self._active = False
        self._reason: Optional[str] = None
        self._lock = threading.Lock()
        self.settings = get_v2_settings()
        self.log = get_logger("safe_mode")

    def activate(self, reason: str):
        """Activates SAFE MODE."""
        with self._lock:
            if not self._active:
                self._active = True
                self._reason = reason
                self.log.critical("INSTITUTIONAL SAFE MODE ACTIVATED", extra={"reason": reason})

    def deactivate(self):
        """Deactivates SAFE MODE."""
        with self._lock:
            if self._active:
                self._active = False
                self._reason = None
                self.log.info("INSTITUTIONAL SAFE MODE DEACTIVATED")

    def is_active(self) -> bool:
        if not self.settings.V2_INSTITUTIONAL_SAFE_MODE_ENABLED:
            return False
        with self._lock:
            return self._active

    def get_reason(self) -> Optional[str]:
        with self._lock:
            return self._reason

    def can_open(self) -> bool:
        """Returns True if OPEN orders are allowed."""
        return not self.is_active()

    def can_close(self) -> bool:
        """CLOSE orders are usually allowed even in safe mode for risk management."""
        return True
