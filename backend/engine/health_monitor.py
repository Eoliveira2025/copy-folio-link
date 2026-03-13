"""
Connection Health Monitor — monitors MT5 connections with latency-aware checks.
Publishes health status and triggers reconnection for stale connections.
"""

from __future__ import annotations
import time
import logging
import threading
import json
from datetime import datetime, timezone
import redis

from engine.config import get_engine_settings
from engine.metrics import get_metrics

settings = get_engine_settings()
logger = logging.getLogger("engine.health_monitor")

HEALTH_KEY_PREFIX = "copytrade:health"


class HealthMonitor(threading.Thread):
    """
    Monitors all active MT5 connections by checking Redis heartbeat keys.
    Publishes queue depth metrics for the metrics system.
    """

    def __init__(self):
        super().__init__(daemon=True, name="HealthMonitor")
        self.running = False
        self.redis_client = redis.from_url(settings.REDIS_URL)
        self._metrics = get_metrics()

    def run(self):
        self.running = True
        logger.info(f"Health Monitor started, checking every {settings.HEALTH_CHECK_INTERVAL_S}s")

        while self.running:
            try:
                # Check heartbeats
                keys = self.redis_client.keys(f"{HEALTH_KEY_PREFIX}:heartbeat:*")
                stale_count = 0

                for key in keys:
                    data = self.redis_client.get(key)
                    if not data:
                        continue

                    info = json.loads(data)
                    last_beat = datetime.fromisoformat(info.get("timestamp", ""))
                    age = (datetime.now(timezone.utc) - last_beat).total_seconds()

                    if age > settings.HEARTBEAT_TTL_S:
                        account_id = info.get("account_id", "")
                        logger.warning(f"Stale connection: {account_id} (age={age:.0f}s)")
                        self.redis_client.publish(
                            "copytrade:reconnect",
                            json.dumps({"account_id": account_id, "reason": "heartbeat_timeout"})
                        )
                        stale_count += 1

                # Measure queue depths
                queue_keys = self.redis_client.keys("copytrade:execute:*")
                total_depth = 0
                for qk in queue_keys:
                    total_depth += self.redis_client.llen(qk)

                self._metrics.set_gauges(queue_depth=total_depth)

                # Publish summary
                self.redis_client.set(
                    f"{HEALTH_KEY_PREFIX}:summary",
                    json.dumps({
                        "total_connections": len(keys),
                        "stale_connections": stale_count,
                        "total_queue_depth": total_depth,
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
        ex=settings.HEARTBEAT_TTL_S * 2,
    )
