"""InstitutionalHeartbeatService — Robust VPS-to-Ubuntu connectivity."""

from __future__ import annotations
import threading
import time
import json
from uuid import UUID
from typing import Dict, List, Callable
from ..config import get_v2_settings
from ..redis_client import get_redis, k
from ..utils.logger import get_logger

class InstitutionalHeartbeatService(threading.Thread):
    """Sends institutional heartbeat to Redis for the Linux backend to monitor."""

    def __init__(self, vps_id: str, get_stats: Callable[[], Dict]):
        super().__init__(name="v2-heartbeat", daemon=True)
        self.vps_id = vps_id
        self.get_stats = get_stats
        self.settings = get_v2_settings()
        self.log = get_logger("heartbeat")
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def run(self):
        self.log.info("institutional heartbeat started", extra={"vps_id": self.vps_id})
        r = get_redis()
        
        while not self._stop.is_set():
            try:
                stats = self.get_stats()
                payload = {
                    "vps_id": self.vps_id,
                    "timestamp": time.time(),
                    "stats": stats,
                    "status": "ONLINE"
                }
                
                # Publish heartbeat
                key = k(f"vps:{self.vps_id}:heartbeat")
                r.setex(key, 15, json.dumps(payload))
                
                # Also publish to a channel for real-time monitoring
                r.publish(k("vps:heartbeat"), json.dumps(payload))
                
            except Exception as e:
                self.log.error("heartbeat send failed", exc_info=e)
            
            self._stop.wait(self.settings.V2_HEARTBEAT_INTERVAL_S)
