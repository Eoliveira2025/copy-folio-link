"""
Result Tracker — subscribes to execution results and persists to PostgreSQL.
"""

from __future__ import annotations
import logging
import time
import json
import threading
from datetime import datetime, timezone
import redis
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from agent.config import get_agent_settings

settings = get_agent_settings()
logger = logging.getLogger("agent.result_tracker")

try:
    import orjson
    def _loads(s) -> dict:
        return orjson.loads(s)
except ImportError:
    _loads = json.loads


class ResultTracker(threading.Thread):
    """Subscribes to copytrade:results and persists to trade_copies table."""

    def __init__(self):
        super().__init__(daemon=True, name="ResultTracker")
        self.running = False
        self.redis_client = redis.from_url(settings.REDIS_URL)
        self.db_engine = create_engine(settings.DATABASE_URL_SYNC, pool_size=5)

    def _persist_result(self, order: dict):
        with Session(self.db_engine) as db:
            db.execute(text("""
                INSERT INTO trade_copies (
                    id, trade_event_id, mt5_account_id, client_ticket,
                    volume, price, status, error_message,
                    latency_ms, executed_at
                ) VALUES (
                    :id, :event_id, :mt5_id, :ticket,
                    :volume, :price, :status, :error,
                    :latency_ms, :executed_at
                )
                ON CONFLICT (id) DO UPDATE SET
                    status = EXCLUDED.status,
                    error_message = EXCLUDED.error_message,
                    latency_ms = EXCLUDED.latency_ms
            """), {
                "id": order.get("order_id", ""),
                "event_id": order.get("event_id", ""),
                "mt5_id": order.get("client_mt5_account_id", ""),
                "ticket": order.get("master_ticket", 0),
                "volume": order.get("volume", 0),
                "price": order.get("executed_price") or order.get("price", 0),
                "status": order.get("status", "failed"),
                "error": order.get("error"),
                "latency_ms": round(order.get("latency_total_ms", 0)) or None,
                "executed_at": datetime.fromtimestamp(
                    order.get("executed_at") or time.time(), tz=timezone.utc
                ).isoformat(),
            })
            db.commit()

    def run(self):
        self.running = True
        logger.info("Result Tracker started")

        while self.running:
            pubsub = None
            try:
                pubsub = self.redis_client.pubsub()
                pubsub.subscribe("copytrade:results")

                for message in pubsub.listen():
                    if not self.running:
                        break
                    if message["type"] != "message":
                        continue

                    try:
                        order = _loads(message["data"])
                        self._persist_result(order)
                    except Exception as e:
                        logger.error(f"Error persisting result: {e}")

            except redis.ConnectionError:
                logger.warning("Redis connection lost, reconnecting...")
                time.sleep(1)
                try:
                    self.redis_client = redis.from_url(settings.REDIS_URL)
                except Exception:
                    pass
            except Exception as e:
                if self.running:
                    logger.error(f"ResultTracker error: {e}", exc_info=True)
                    time.sleep(1)
            finally:
                if pubsub:
                    try:
                        pubsub.close()
                    except Exception:
                        pass

    def stop(self):
        self.running = False
