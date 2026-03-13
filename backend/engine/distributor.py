"""
Trade Distributor — consumes TradeEvents from Redis and fans out CopyOrders
to per-client execution queues.

Flow:
  1. Subscribe to copytrade:events:* channels
  2. On event, query DB for all active clients subscribed to this master's strategy
  3. Calculate proportional lot size for each client
  4. Push CopyOrder to per-client Redis queue: copytrade:execute:{client_mt5_id}
"""

from __future__ import annotations
import logging
import threading
from typing import Dict, List
import redis
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from engine.config import get_engine_settings
from engine.models import TradeEvent, CopyOrder, TradeAction
from engine.lot_calculator import calculate_lot_size

settings = get_engine_settings()
logger = logging.getLogger("engine.distributor")

ENGINE_QUEUE_PREFIX = "copytrade:execute"


class TradeDistributor(threading.Thread):
    """Listens for master trade events and distributes CopyOrders to client queues."""

    def __init__(self):
        super().__init__(daemon=True, name="TradeDistributor")
        self.running = False
        self.redis_client = redis.from_url(settings.REDIS_URL)
        self.db_engine = create_engine(settings.DATABASE_URL_SYNC)
        # Cache: master_account_id → list of client info dicts
        self._client_cache: Dict[str, List[dict]] = {}
        self._cache_ttl = 60  # seconds
        self._last_cache_refresh: Dict[str, float] = {}

    def _get_clients_for_master(self, master_account_id: str) -> List[dict]:
        """
        Query all active client MT5 accounts subscribed to the strategy
        that maps to this master account.
        """
        import time
        now = time.time()

        # Use cache if fresh
        if master_account_id in self._client_cache:
            if now - self._last_cache_refresh.get(master_account_id, 0) < self._cache_ttl:
                return self._client_cache[master_account_id]

        with Session(self.db_engine) as db:
            # Find strategy for this master
            rows = db.execute(text("""
                SELECT
                    ma.login AS client_login,
                    ma.id AS client_mt5_id,
                    ma.server AS client_server,
                    ma.balance AS client_balance,
                    s.level AS strategy_level,
                    master.balance AS master_balance
                FROM mt5_accounts ma
                JOIN user_strategies us ON us.user_id = ma.user_id AND us.is_active = true
                JOIN strategies s ON s.id = us.strategy_id
                JOIN master_accounts master ON master.strategy_id = s.id
                WHERE master.id = :master_id
                  AND ma.status = 'connected'
            """), {"master_id": master_account_id}).fetchall()

            clients = [
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

        self._client_cache[master_account_id] = clients
        self._last_cache_refresh[master_account_id] = now
        logger.info(f"Refreshed client cache for master {master_account_id}: {len(clients)} clients")
        return clients

    def _distribute_event(self, event: TradeEvent):
        """Fan out a single TradeEvent to all subscribed client accounts."""
        clients = self._get_clients_for_master(event.master_account_id)

        if not clients:
            logger.warning(f"No clients for master {event.master_account_id}, skipping event {event.event_id}")
            return

        for client in clients:
            # Calculate proportional lot size
            volume = calculate_lot_size(
                master_volume=event.volume,
                master_balance=client["master_balance"],
                client_balance=client["client_balance"],
                strategy_level=client["strategy_level"],
            )

            if volume <= 0 and event.action == TradeAction.OPEN:
                logger.info(f"Skipping client {client['client_login']}: balance too low for min lot")
                continue

            # For CLOSE/MODIFY, volume comes from original position (handled by executor)
            if event.action in (TradeAction.CLOSE, TradeAction.MODIFY):
                volume = event.volume  # executor will find client's matching ticket

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
            )

            # Push to per-client execution queue
            queue_key = f"{ENGINE_QUEUE_PREFIX}:{client['client_mt5_id']}"
            self.redis_client.lpush(queue_key, order.to_json())
            logger.info(
                f"Dispatched {event.action.value} {event.symbol} → client {client['client_login']} "
                f"vol={volume} queue={queue_key}"
            )

    def run(self):
        """Subscribe to all master event channels and distribute."""
        self.running = True
        pubsub = self.redis_client.pubsub()
        pubsub.psubscribe("copytrade:events:*")

        logger.info("Trade Distributor started, subscribing to copytrade:events:*")

        for message in pubsub.listen():
            if not self.running:
                break

            if message["type"] != "pmessage":
                continue

            try:
                event = TradeEvent.from_json(message["data"])
                logger.info(f"Received event: {event.action.value} {event.symbol} ticket={event.ticket}")
                self._distribute_event(event)
            except Exception as e:
                logger.error(f"Error processing event: {e}", exc_info=True)

    def stop(self):
        self.running = False
        logger.info("Trade Distributor stopped")
