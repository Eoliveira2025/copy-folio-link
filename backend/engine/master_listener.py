"""
Master Trade Listener — polls a master MT5 account for position changes
and publishes TradeEvents to Redis.

Each master account gets its own listener running in a separate thread/process.
"""

from __future__ import annotations
import time
import logging
import threading
from typing import Dict, Optional
import redis
import MetaTrader5 as mt5

from engine.config import get_engine_settings
from engine.models import TradeEvent, TradeAction, TradeDirection

settings = get_engine_settings()
logger = logging.getLogger("engine.master_listener")

# Redis channel pattern: copytrade:events:{master_account_id}
CHANNEL_PREFIX = "copytrade:events"


class PositionSnapshot:
    """Tracks known positions to detect opens, closes, and modifications."""

    def __init__(self):
        self.positions: Dict[int, dict] = {}  # ticket → position info

    def diff(self, current_positions: list[dict]) -> list[TradeEvent]:
        """Compare current positions against last snapshot, emit events."""
        events: list[TradeEvent] = []
        current_tickets = {}

        for pos in current_positions:
            ticket = pos["ticket"]
            current_tickets[ticket] = pos

            if ticket not in self.positions:
                # New position — OPEN event
                events.append(self._make_event(pos, TradeAction.OPEN))
            else:
                # Check for SL/TP modification
                old = self.positions[ticket]
                if pos.get("sl") != old.get("sl") or pos.get("tp") != old.get("tp"):
                    events.append(self._make_event(pos, TradeAction.MODIFY))

        # Positions that disappeared — CLOSE events
        for ticket, old_pos in self.positions.items():
            if ticket not in current_tickets:
                events.append(self._make_event(old_pos, TradeAction.CLOSE))

        # Update snapshot
        self.positions = current_tickets
        return events

    @staticmethod
    def _make_event(pos: dict, action: TradeAction) -> TradeEvent:
        direction = TradeDirection.BUY if pos.get("type", 0) == 0 else TradeDirection.SELL
        return TradeEvent(
            master_login=pos.get("login", 0),
            ticket=pos["ticket"],
            symbol=pos.get("symbol", ""),
            action=action,
            direction=direction,
            volume=pos.get("volume", 0.0),
            price=pos.get("price_open", 0.0),
            sl=pos.get("sl"),
            tp=pos.get("tp"),
        )


class MasterListener(threading.Thread):
    """
    Continuously polls a master MT5 account and publishes trade events to Redis.

    Since MetaTrader5 Python API only supports one connection per process,
    each MasterListener runs in a subprocess (spawned by the orchestrator).
    This class uses threading for the polling loop within that subprocess.
    """

    def __init__(self, master_account_id: str, login: int, password: str, server: str):
        super().__init__(daemon=True, name=f"Listener-{login}")
        self.master_account_id = master_account_id
        self.login = login
        self.password = password
        self.server = server
        self.snapshot = PositionSnapshot()
        self.running = False
        self.redis_client: Optional[redis.Redis] = None
        self._channel = f"{CHANNEL_PREFIX}:{master_account_id}"

    def connect_mt5(self) -> bool:
        """Initialize MT5 terminal and log in."""
        if not mt5.initialize():
            logger.error(f"[{self.login}] MT5 initialize failed: {mt5.last_error()}")
            return False

        authorized = mt5.login(self.login, password=self.password, server=self.server)
        if not authorized:
            logger.error(f"[{self.login}] MT5 login failed: {mt5.last_error()}")
            mt5.shutdown()
            return False

        logger.info(f"[{self.login}] Connected to {self.server}")
        return True

    def get_positions(self) -> list[dict]:
        """Fetch all open positions from MT5."""
        positions = mt5.positions_get()
        if positions is None:
            return []
        return [
            {
                "ticket": p.ticket,
                "symbol": p.symbol,
                "type": p.type,  # 0=BUY, 1=SELL
                "volume": p.volume,
                "price_open": p.price_open,
                "sl": p.sl,
                "tp": p.tp,
                "login": self.login,
            }
            for p in positions
        ]

    def run(self):
        """Main polling loop."""
        self.redis_client = redis.from_url(settings.REDIS_URL)
        self.running = True

        if not self.connect_mt5():
            logger.error(f"[{self.login}] Cannot start listener — connection failed")
            return

        logger.info(f"[{self.login}] Listener started, polling every {settings.MASTER_POLL_INTERVAL_MS}ms")

        # Initial snapshot (don't emit events for existing positions)
        initial = self.get_positions()
        self.snapshot.positions = {p["ticket"]: p for p in initial}
        logger.info(f"[{self.login}] Initial snapshot: {len(initial)} open positions")

        while self.running:
            try:
                current = self.get_positions()
                events = self.snapshot.diff(current)

                for event in events:
                    event.master_account_id = self.master_account_id
                    # Publish to Redis channel
                    self.redis_client.publish(self._channel, event.to_json())
                    # Also push to a persistent queue for reliability
                    self.redis_client.lpush(f"copytrade:queue:{self.master_account_id}", event.to_json())
                    logger.info(f"[{self.login}] Event: {event.action.value} {event.symbol} ticket={event.ticket} vol={event.volume}")

            except Exception as e:
                logger.error(f"[{self.login}] Poll error: {e}")
                # Attempt reconnection
                try:
                    mt5.shutdown()
                    time.sleep(2)
                    self.connect_mt5()
                except Exception:
                    pass

            time.sleep(settings.MASTER_POLL_INTERVAL_MS / 1000.0)

    def stop(self):
        self.running = False
        mt5.shutdown()
        logger.info(f"[{self.login}] Listener stopped")
