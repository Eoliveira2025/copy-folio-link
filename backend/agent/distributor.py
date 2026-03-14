"""
Trade Distributor — consumes master TradeEvents from Redis and fans out
CopyOrders to per-client execution queues.

Handles the strategy-based lot calculation:
  - Most strategies: exact 1:1 copy
  - expert_pro: proportional calculation
"""

from __future__ import annotations
import logging
import time
import threading
import json
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List
import redis
import uuid
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from agent.config import get_agent_settings
from agent.lot_calculator import calculate_lot_size

settings = get_agent_settings()
logger = logging.getLogger("agent.distributor")

EXECUTE_QUEUE_PREFIX = "copytrade:execute"

try:
    import orjson
    def _dumps(d: dict) -> str:
        return orjson.dumps(d).decode()
    def _loads(s) -> dict:
        return orjson.loads(s)
except ImportError:
    _dumps = json.dumps
    _loads = json.loads


class ClientCache:
    """In-memory cache of clients subscribed to each master account."""

    def __init__(self, db_engine, ttl_s: int = 30):
        self._db_engine = db_engine
        self._ttl_s = ttl_s
        self._cache: Dict[str, List[dict]] = {}
        self._timestamps: Dict[str, float] = {}
        self._lock = threading.Lock()

    def get(self, master_account_id: str) -> List[dict]:
        with self._lock:
            now = time.time()
            if master_account_id in self._cache:
                if now - self._timestamps.get(master_account_id, 0) < self._ttl_s:
                    return self._cache[master_account_id]

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
        with Session(self._db_engine) as db:
            rows = db.execute(text("""
                SELECT
                    ma.login AS client_login,
                    ma.id AS client_mt5_id,
                    ma.server AS client_server,
                    ma.balance AS client_balance,
                    s.level AS strategy_level,
                    s.risk_multiplier,
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
                    "strategy_level": str(row.strategy_level),
                    "risk_multiplier": row.risk_multiplier or 1.0,
                    "master_balance": row.master_balance or 0.0,
                }
                for row in rows
            ]


class TradeDistributor(threading.Thread):
    """Subscribes to copytrade:events:* and distributes orders to execution queues."""

    def __init__(self):
        super().__init__(daemon=True, name="TradeDistributor")
        self.running = False
        self.redis_client = redis.Redis.from_url(
            settings.REDIS_URL,
            socket_keepalive=True,
            socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
        )
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
        self._events_distributed = 0
        self._orders_created = 0

    def _distribute_event(self, event: dict):
        """Fan out a single TradeEvent to all subscribed clients."""
        dist_start = time.time()
        master_account_id = event.get("master_account_id", "")

        clients = self.client_cache.get(master_account_id)
        if not clients:
            logger.warning(f"No clients for master {master_account_id}")
            return

        orders = []
        action = event.get("action", "open")

        for client in clients:
            if action == "open":
                volume = calculate_lot_size(
                    master_volume=event["volume"],
                    master_balance=client["master_balance"],
                    client_balance=client["client_balance"],
                    strategy_level=client["strategy_level"],
                    risk_multiplier=client.get("risk_multiplier", 1.0),
                    min_lot=settings.MIN_LOT,
                    max_lot=settings.MAX_LOT,
                    lot_step=settings.LOT_STEP,
                )
                if volume <= 0:
                    continue
            else:
                volume = event["volume"]

            order = {
                "order_id": uuid.uuid4().hex,
                "event_id": event.get("event_id", ""),
                "client_mt5_account_id": client["client_mt5_id"],
                "client_login": client["client_login"],
                "client_server": client["client_server"],
                "symbol": event["symbol"],
                "action": action,
                "direction": event["direction"],
                "volume": volume,
                "price": event.get("price", 0.0),
                "sl": event.get("sl"),
                "tp": event.get("tp"),
                "master_ticket": event["ticket"],
                "magic_number": event.get("magic_number", 123456),
                "status": "pending",
                "attempt": 0,
                "max_attempts": settings.MAX_RETRY_ATTEMPTS,
                "max_slippage_points": settings.MAX_SLIPPAGE_POINTS,
                "master_price": event.get("price", 0.0),
                "event_detected_at": event.get("detected_at", 0.0),
                "distributed_at": dist_start,
                "slippage_points": 0.0,
                "executed_price": 0.0,
            }
            orders.append(order)
            self._orders_created += 1

        if not orders:
            return

        # Batch enqueue with Redis pipeline
        now = time.time()
        pipe = self.redis_client.pipeline(transaction=False)
        for order in orders:
            order["enqueued_at"] = now
            queue_key = f"{EXECUTE_QUEUE_PREFIX}:{order['client_mt5_account_id']}"
            pipe.lpush(queue_key, _dumps(order))
        pipe.execute()

        dist_latency_ms = (time.time() - dist_start) * 1000
        self._events_distributed += 1

        logger.info(
            f"Distributed {action} {event['symbol']} → {len(orders)} clients "
            f"in {dist_latency_ms:.1f}ms"
        )

    def run(self):
        self.running = True
        logger.info("Trade Distributor started")

        while self.running:
            pubsub = None
            try:
                pubsub = self.redis_client.pubsub()
                pubsub.psubscribe("copytrade:events:*")

                for message in pubsub.listen():
                    if not self.running:
                        break
                    if message["type"] != "pmessage":
                        continue

                    try:
                        event = _loads(message["data"])
                        self._executor.submit(self._safe_distribute, event)
                    except Exception as e:
                        logger.error(f"Event parse error: {e}")

            except redis.ConnectionError:
                logger.warning("Redis connection lost in distributor, reconnecting...")
                time.sleep(1)
                try:
                    self.redis_client = redis.Redis.from_url(settings.REDIS_URL)
                except Exception:
                    pass
            except Exception as e:
                if self.running:
                    logger.error(f"Distributor error: {e}", exc_info=True)
                    time.sleep(1)
            finally:
                if pubsub:
                    try:
                        pubsub.close()
                    except Exception:
                        pass

    def _safe_distribute(self, event: dict):
        try:
            self._distribute_event(event)
        except Exception as e:
            logger.error(f"Distribution error: {e}", exc_info=True)

    def stop(self):
        self.running = False
        self._executor.shutdown(wait=False)
