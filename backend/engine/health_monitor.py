"""
Connection Health Monitor — periodically checks MT5 terminal connections
and triggers reconnection when needed.

Publishes health status to Redis for dashboard consumption.
"""

from __future__ import annotations
import time
import logging
import threading
import json
from datetime import datetime, timezone
import redis

from engine.config import get_engine_settings

settings = get_engine_settings()
logger = logging.getLogger("engine.health_monitor")

HEALTH_KEY_PREFIX = "copytrade:health"


class HealthStatus:
    def __init__(self, account_id: str, login: int, server: str):
        self.account_id = account_id
        self.login = login
        self.server = server
        self.is_connected = False
        self.last_heartbeat: str = ""
        self.uptime_seconds: int = 0
        self.reconnect_count: int = 0
        self.error: str | None = None

    def to_dict(self) -> dict:
        return {
            "account_id": self.account_id,
            "login": self.login,
            "server": self.server,
            "is_connected": self.is_connected,
            "last_heartbeat": self.last_heartbeat,
            "uptime_seconds": self.uptime_seconds,
            "reconnect_count": self.reconnect_count,
            "error": self.error,
        }


class HealthMonitor(threading.Thread):
    """
    Monitors all active MT5 connections by checking Redis heartbeat keys.
    Workers and listeners update their heartbeat key periodically.
    If a heartbeat goes stale, the monitor flags it for reconnection.
    """

    def __init__(self):
        super().__init__(daemon=True, name="HealthMonitor")
        self.running = False
        self.redis_client = redis.from_url(settings.REDIS_URL)

    def run(self):
        self.running = True
        logger.info(f"Health Monitor started, checking every {settings.HEALTH_CHECK_INTERVAL_S}s")

        while self.running:
            try:
                # Scan for all heartbeat keys
                keys = self.redis_client.keys(f"{HEALTH_KEY_PREFIX}:heartbeat:*")

                for key in keys:
                    data = self.redis_client.get(key)
                    if not data:
                        continue

                    info = json.loads(data)
                    last_beat = datetime.fromisoformat(info.get("timestamp", ""))
                    age = (datetime.now(timezone.utc) - last_beat).total_seconds()

                    if age > settings.HEALTH_CHECK_INTERVAL_S * 3:
                        # Connection is stale — flag for reconnection
                        account_id = info.get("account_id", "")
                        logger.warning(f"Stale connection detected: {account_id} (age={age:.0f}s)")
                        self.redis_client.publish(
                            "copytrade:reconnect",
                            json.dumps({"account_id": account_id, "reason": "heartbeat_timeout"})
                        )

                # Publish aggregated health status
                self.redis_client.set(
                    f"{HEALTH_KEY_PREFIX}:summary",
                    json.dumps({
                        "total_connections": len(keys),
                        "checked_at": datetime.now(timezone.utc).isoformat(),
                    }),
                    ex=settings.HEALTH_CHECK_INTERVAL_S * 5,
                )

            except Exception as e:
                logger.error(f"Health check error: {e}", exc_info=True)

            time.sleep(settings.HEALTH_CHECK_INTERVAL_S)

    def stop(self):
        self.running = False


def send_heartbeat(redis_client: redis.Redis, account_id: str, login: int, role: str = "worker"):
    """Called by listeners/workers to report they're alive."""
    redis_client.set(
        f"{HEALTH_KEY_PREFIX}:heartbeat:{account_id}",
        json.dumps({
            "account_id": account_id,
            "login": login,
            "role": role,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }),
        ex=settings.HEALTH_CHECK_INTERVAL_S * 5,
    )
