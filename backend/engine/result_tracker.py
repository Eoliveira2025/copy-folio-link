"""
Result Tracker — consumes execution results from Redis and persists them
to the database for audit trail and dashboard display.
"""

from __future__ import annotations
import logging
import threading
import redis
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from engine.config import get_engine_settings
from engine.models import CopyOrder, CopyStatus

settings = get_engine_settings()
logger = logging.getLogger("engine.result_tracker")


class ResultTracker(threading.Thread):
    """Subscribes to copytrade:results channel and persists to DB."""

    def __init__(self):
        super().__init__(daemon=True, name="ResultTracker")
        self.running = False
        self.redis_client = redis.from_url(settings.REDIS_URL)
        self.db_engine = create_engine(settings.DATABASE_URL_SYNC)

    def _persist_result(self, order: CopyOrder):
        """Write copy result to trade_copies table."""
        with Session(self.db_engine) as db:
            from sqlalchemy import text
            db.execute(text("""
                INSERT INTO trade_copies (
                    id, trade_event_id, mt5_account_id, client_ticket,
                    volume, price, status, error_message, latency_ms, executed_at
                ) VALUES (
                    :id, :event_id, :mt5_id, :ticket,
                    :volume, :price, :status, :error, :latency, :executed_at
                )
                ON CONFLICT (id) DO UPDATE SET
                    status = :status,
                    error_message = :error,
                    executed_at = :executed_at
            """), {
                "id": order.order_id,
                "event_id": order.event_id,
                "mt5_id": order.client_mt5_account_id,
                "ticket": None,  # filled from MT5 response
                "volume": order.volume,
                "price": order.price,
                "status": order.status.value,
                "error": order.error,
                "latency": None,
                "executed_at": datetime.now(timezone.utc).isoformat() if order.status == CopyStatus.EXECUTED else None,
            })
            db.commit()

    def run(self):
        self.running = True
        pubsub = self.redis_client.pubsub()
        pubsub.subscribe("copytrade:results")

        logger.info("Result Tracker started")

        for message in pubsub.listen():
            if not self.running:
                break
            if message["type"] != "message":
                continue

            try:
                order = CopyOrder.from_json(message["data"])
                self._persist_result(order)
                logger.info(f"Persisted result: {order.order_id} status={order.status.value}")
            except Exception as e:
                logger.error(f"Error persisting result: {e}", exc_info=True)

    def stop(self):
        self.running = False
