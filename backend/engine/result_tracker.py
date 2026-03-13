"""
Result Tracker — consumes execution results with full latency data
and persists to DB for audit trail and dashboard.
"""

from __future__ import annotations
import logging
import time
import threading
import redis
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from engine.config import get_engine_settings
from engine.models import CopyOrder, CopyStatus

settings = get_engine_settings()
logger = logging.getLogger("engine.result_tracker")


class ResultTracker(threading.Thread):
    """Subscribes to copytrade:results and persists with latency metrics."""

    def __init__(self):
        super().__init__(daemon=True, name="ResultTracker")
        self.running = False
        self.redis_client = redis.from_url(settings.REDIS_URL)
        self.db_engine = create_engine(settings.DATABASE_URL_SYNC, pool_size=5)
        self._batch: list[CopyOrder] = []
        self._batch_size = 50
        self._last_flush = 0.0

    def _persist_result(self, order: CopyOrder):
        """Write copy result with latency data."""
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
                ON CONFLICT (id, executed_at) DO UPDATE SET
                    status = EXCLUDED.status,
                    error_message = EXCLUDED.error_message,
                    latency_ms = EXCLUDED.latency_ms
            """), {
                "id": order.order_id,
                "event_id": order.event_id,
                "mt5_id": order.client_mt5_account_id,
                "ticket": order.master_ticket,
                "volume": order.volume,
                "price": order.executed_price or order.price,
                "status": order.status.value,
                "error": order.error,
                "latency_ms": round(order.latency_total_ms) if order.latency_total_ms else None,
                "executed_at": datetime.fromtimestamp(
                    order.executed_at or time.time(), tz=timezone.utc
                ).isoformat(),
            })
            db.commit()

    def run(self):
        """Subscribe to results with auto-reconnect on Redis failure."""
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
                        order = CopyOrder.from_json(message["data"])
                        self._persist_result(order)

                        if order.latency_total_ms > 0:
                            logger.info(
                                f"Result: {order.order_id[:8]} {order.status.value} "
                                f"total={order.latency_total_ms:.1f}ms slip={order.slippage_points:.1f}pts"
                            )
                    except Exception as e:
                        logger.error(f"Error persisting result: {e}", exc_info=True)

            except redis.ConnectionError as e:
                logger.warning(f"Redis connection lost in ResultTracker: {e}. Reconnecting in 1s...")
                time.sleep(1)
                try:
                    self.redis_client = redis.from_url(settings.REDIS_URL)
                except Exception:
                    pass
            except Exception as e:
                if self.running:
                    logger.error(f"ResultTracker unexpected error: {e}", exc_info=True)
                    time.sleep(1)
            finally:
                if pubsub:
                    try:
                        pubsub.close()
                    except Exception:
                        pass

    def stop(self):
        self.running = False
