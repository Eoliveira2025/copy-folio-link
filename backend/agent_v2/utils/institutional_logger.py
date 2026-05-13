"""Institutional Logging implementation."""

import logging
import json
import os
from datetime import datetime
from ..config import get_v2_settings

class InstitutionalLogger:
    """Structured JSON logger for institutional events."""

    def __init__(self, name: str):
        self.settings = get_v2_settings()
        self.logger = logging.getLogger(f"v2.institutional.{name}")
        self.name = name
        
        # Ensure logs dir exists
        log_dir = os.path.join(self.settings.V2_LOGS_DIR, "structured")
        os.makedirs(log_dir, exist_ok=True)
        
        self.log_path = os.path.join(log_dir, f"{name}.json")
        
        # File handler
        fh = logging.FileHandler(self.log_path)
        fh.setFormatter(logging.Formatter('%(message)s'))
        self.logger.addHandler(fh)
        self.logger.setLevel(logging.INFO)

    def log_event(self, event_type: str, data: dict):
        payload = {
            "ts": datetime.utcnow().isoformat(),
            "event": event_type,
            "vps_id": self.settings.V2_VPS_ID,
            "data": data
        }
        self.logger.info(json.dumps(payload))

# Global instances for core events
execution_logs = InstitutionalLogger("execution")
reconnect_logs = InstitutionalLogger("reconnect")
recovery_logs = InstitutionalLogger("recovery")
resource_logs = InstitutionalLogger("resource")
safe_mode_logs = InstitutionalLogger("safe_mode")
