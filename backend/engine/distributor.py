"""
Ultra-Low-Latency Trade Distributor

Consumes TradeEvents and fans out CopyOrders to execution queues with:
  - Thread pool for parallel client lookup + lot calculation
  - Redis pipeline for batch queue writes
  - Cached client lists (refreshed every 30s)
  - Latency tracking per hop

Target: <5ms distribution latency (event → all orders enqueued)
"""

from __future__ import annotations
import logging
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List
import redis

from engine.config import get_engine_settings
from engine.models import TradeEvent, CopyOrder, TradeAction
from engine.lot_calculator import calculate_lot_size
from engine.metrics import get_metrics

settings = get_engine_settings()
logger = logging.getLogger("engine.distributor")

EXECUTE_QUEUE_PREFIX = "copytrade:execute"


class ClientCache:
    """
    In-memory client list cache with TTL refresh.
    Avoids DB round-trip on every trade event.
    """

    def __init__(self, db_engine, ttl_s: int = 30):
        self._db_engine = db_engine
        self._ttl_s = ttl_s
        self._cache: Dict[str, List[dict]] = {}  # master_id → clients
        self._timestamps: Dict[str, float] = {}
        self._lock = threading.Lock()

    def get(self, master_account_id: str) -> List[dict]:
        with self._lock:
            now = time.time()
            if master_account_id in self._cache:
                if now - self._timestamps.get(master_account_id, 0) < self._ttl_s:
                    return self._cache[master_account_id]

        # Refresh outside lock
        clients = self._fetch_from_db(master_account_id)
        with self._lock:
            self._cache[master_account_id] = clients
            self._timestamps[master_account_id] = time.time()
        return clients

    def invalidate(self, master_account_id: str = None):
        with self._lock:
            if master_account_id:
                self._cache.pop(master_account_id, None)
            else:
                self._cache.clear()

    def _fetch_from_db(self, master_account_id: str) -> List[dict]:
        from sqlalchemy.orm import Session
        from sqlalchemy import text

        with Session(self._db_engine) as db:
            rows = db.execute(text("""
                SELECT
                    ma.login AS client_login,
                    ma.id AS client_mt5_id,
                    ma.server AS client_server,
                    ma.balance AS client_balance,
                    s.name AS strategy_level,
                    master.balance AS master_balance
                FROM mt5_accounts ma
                JOIN user_strategies us ON us.user_id = ma.user_id AND us.is_active = true
                JOIN strategies s ON s.id = us.strategy_id
                JOIN master_accounts master ON master.strategy_id = s.id
                WHERE master.id = :master_id
                  AND ma.status = 'connected'
            """), {"master_id": master_account_id}).fetchall()

            return [
                {
                    "client_login": row.client_login,
                    "client_mt5_id": str(row.client_mt5_id),
                    "client_server": row.client_server,
                    "client_balance": row.client_balance or 0.0,
                    "strategy_level": row.strategy_level,
                    "master_balance": row.master_balance or 0.0,
                }
                for row in rows
            ]


class TradeDistributor(threading.Thread):
    """
    Ultra-fast trade event distributor with parallel fan-out.

    Pipeline:
      Redis pub/sub event → client lookup (cached) → lot calc → batch enqueue
    """

    def __init__(self):
        super().__init__(daemon=True, name="TradeDistributor")
        self.running = False
        self.redis_client = redis.Redis.from_url(
            settings.REDIS_URL,
            socket_keepalive=True,
            socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
        )

        from sqlalchemy import create_engine
        self.db_engine = create_engine(
            settings.DATABASE_URL_SYNC,
            pool_size=10,
            pool_pre_ping=True,
        )
        self.client_cache = ClientCache(self.db_engine, ttl_s=30)
        self._executor = ThreadPoolExecutor(
            max_workers=settings.DISTRIBUTOR_THREAD_POOL_SIZE,
            thread_name_prefix="dist",
        )
        self._metrics = get_metrics()

    def _distribute_event(self, event: TradeEvent):
        """Fan out a single TradeEvent to all subscribed clients."""
        dist_start = time.time()

        clients = self.client_cache.get(event.master_account_id)
        if not clients:
            logger.warning(f"No clients for master {event.master_account_id}")
            return

        orders: List[CopyOrder] = []

        for client in clients:
            # Calculate lot size
            if event.action == TradeAction.OPEN:
                volume = calculate_lot_size(
                    master_volume=event.volume,
                    master_balance=client["master_balance"],
                    client_balance=client["client_balance"],
                    strategy_level=client["strategy_level"],
                )
                if volume <= 0:
                    self._metrics.record_skip()
                    continue
            else:
                volume = event.volume

            order = CopyOrder(
                event_id=event.event_id,
                client_mt5_account_id=client["client_mt5_id"],
                client_login=client["client_login"],
                client_server=client["client_server"],
                symbol=event.symbol,
                action=event.action,
                direction=event.direction,
                volume=volume,
                price=event.price,
                sl=event.sl,
                tp=event.tp,
                master_ticket=event.ticket,
                magic_number=event.magic_number,
                max_slippage_points=settings.MAX_SLIPPAGE_POINTS,
                master_price=event.price,
                event_detected_at=event.detected_at,
                distributed_at=dist_start,
            )
            orders.append(order)
            self._metrics.record_order_created()

        if not orders:
            return

        # ── Batch enqueue with Redis pipeline ──
        now = time.time()
        pipe = self.redis_client.pipeline(transaction=False)
        for order in orders:
            order.enqueued_at = now
            queue_key = f"{EXECUTE_QUEUE_PREFIX}:{order.client_mt5_account_id}"
            pipe.lpush(queue_key, order.to_json())

        pipe.execute()

        dist_latency_ms = (time.time() - dist_start) * 1000
        detect_to_dist_ms = (dist_start - event.detected_at) * 1000

        self._metrics.record_event_distributed(detect_to_dist_ms)

        logger.info(
            f"Distributed {event.action.value} {event.symbol} → {len(orders)} clients "
            f"in {dist_latency_ms:.1f}ms (detect→dist: {detect_to_dist_ms:.1f}ms)"
        )

    def run(self):
        """Subscribe to all master event channels and distribute."""
        self.running = True
        pubsub = self.redis_client.pubsub()
        pubsub.psubscribe("copytrade:events:*")

        logger.info(
            f"Trade Distributor started — pool: {settings.DISTRIBUTOR_THREAD_POOL_SIZE} threads, "
            f"subscribing to copytrade:events:*"
        )

        for message in pubsub.listen():
            if not self.running:
                break

            if message["type"] != "pmessage":
                continue

            try:
                event = TradeEvent.from_json(message["data"])
                # Submit to thread pool for parallel processing
                self._executor.submit(self._safe_distribute, event)
            except Exception as e:
                logger.error(f"Event parse error: {e}", exc_info=True)

    def _safe_distribute(self, event: TradeEvent):
        """Wrapper with error handling for thread pool."""
        try:
            self._distribute_event(event)
        except Exception as e:
            logger.error(f"Distribution error: {e}", exc_info=True)

    def stop(self):
        self.running = False
        self._executor.shutdown(wait=False)
        logger.info("Trade Distributor stopped")
