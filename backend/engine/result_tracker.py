"""
Result Tracker — consumes execution results with full latency data
and persists to DB for audit trail and dashboard.
"""

from __future__ import annotations
import logging
import threading
import json
import redis
from sqlalchemy import create_engine
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
            from sqlalchemy import text
            db.execute(text("""
                INSERT INTO trade_copies (
                    id, trade_event_id, mt5_account_id, client_ticket,
                    volume, price, status, error_message,
                    latency_total_ms, latency_execution_ms,
                    slippage_points, executed_price, master_price,
                    executed_at
                ) VALUES (
                    :id, :event_id, :mt5_id, :ticket,
                    :volume, :price, :status, :error,
                    :latency_total, :latency_exec,
                    :slippage, :exec_price, :master_price,
                    :executed_at
                )
                ON CONFLICT (id) DO UPDATE SET
                    status = :status,
                    error_message = :error,
                    latency_total_ms = :latency_total,
                    slippage_points = :slippage,
                    executed_at = :executed_at
            """), {
                "id": order.order_id,
                "event_id": order.event_id,
                "mt5_id": order.client_mt5_account_id,
                "ticket": order.master_ticket,
                "volume": order.volume,
                "price": order.price,
                "status": order.status.value,
                "error": order.error,
                "latency_total": round(order.latency_total_ms, 2) if order.latency_total_ms else None,
                "latency_exec": round(
                    (order.executed_at - order.dequeued_at) * 1000, 2
                ) if order.executed_at and order.dequeued_at else None,
                "slippage": round(order.slippage_points, 2),
                "exec_price": order.executed_price,
                "master_price": order.master_price,
                "executed_at": datetime.fromtimestamp(order.executed_at, tz=timezone.utc).isoformat()
                    if order.executed_at else None,
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

                if order.latency_total_ms > 0:
                    logger.info(
                        f"Result: {order.order_id[:8]} {order.status.value} "
                        f"total={order.latency_total_ms:.1f}ms slip={order.slippage_points:.1f}pts"
                    )
            except Exception as e:
                logger.error(f"Error persisting result: {e}", exc_info=True)

    def stop(self):
        self.running = False
