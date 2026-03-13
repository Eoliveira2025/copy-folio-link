"""
Ultra-Low-Latency Master Trade Listener

Detects master account trades with <10ms detection latency using:
  1. Continuous 10ms position polling (100 polls/sec)
  2. Order history monitoring for immediate open/close detection
  3. Zero-copy event publishing via Redis pipeline
  4. Monotonic timestamps for accurate latency measurement

Each master account runs its own listener in a dedicated subprocess
(MT5 Python API limitation: one connection per process).
"""

from __future__ import annotations
import time
import logging
import threading
from typing import Dict, List, Optional, Set
import redis

from engine.config import get_engine_settings
from engine.models import TradeEvent, TradeAction, TradeDirection
from engine.metrics import get_metrics

settings = get_engine_settings()
logger = logging.getLogger("engine.master_listener")

CHANNEL_PREFIX = "copytrade:events"
QUEUE_PREFIX = "copytrade:queue"


class PositionSnapshot:
    """
    Ultra-fast position differ.
    Uses dict lookup (O(1)) instead of list iteration for change detection.
    """

    __slots__ = ("positions", "_sl_tp_cache")

    def __init__(self):
        self.positions: Dict[int, dict] = {}  # ticket → position dict
        self._sl_tp_cache: Dict[int, tuple] = {}  # ticket → (sl, tp) for fast modify detect

    def diff(self, current_positions: List[dict], master_login: int) -> List[TradeEvent]:
        """Compare current vs previous snapshot. Returns events for all changes."""
        events: List[TradeEvent] = []
        current_tickets: Dict[int, dict] = {}
        now = time.time()

        for pos in current_positions:
            ticket = pos["ticket"]
            current_tickets[ticket] = pos

            if ticket not in self.positions:
                # ── NEW POSITION ──
                events.append(TradeEvent(
                    master_login=master_login,
                    ticket=ticket,
                    symbol=pos["symbol"],
                    action=TradeAction.OPEN,
                    direction=TradeDirection.BUY if pos["type"] == 0 else TradeDirection.SELL,
                    volume=pos["volume"],
                    price=pos["price_open"],
                    sl=pos.get("sl", 0.0),
                    tp=pos.get("tp", 0.0),
                    magic_number=pos.get("magic", 0),
                    detected_at=now,
                ))
            else:
                # ── CHECK MODIFY (SL/TP change) ──
                cached = self._sl_tp_cache.get(ticket)
                new_sl_tp = (pos.get("sl", 0.0), pos.get("tp", 0.0))
                if cached and cached != new_sl_tp:
                    events.append(TradeEvent(
                        master_login=master_login,
                        ticket=ticket,
                        symbol=pos["symbol"],
                        action=TradeAction.MODIFY,
                        direction=TradeDirection.BUY if pos["type"] == 0 else TradeDirection.SELL,
                        volume=pos["volume"],
                        price=pos["price_open"],
                        sl=new_sl_tp[0],
                        tp=new_sl_tp[1],
                        magic_number=pos.get("magic", 0),
                        detected_at=now,
                    ))

            self._sl_tp_cache[ticket] = (pos.get("sl", 0.0), pos.get("tp", 0.0))

        # ── CLOSED POSITIONS ──
        closed_tickets = set(self.positions.keys()) - set(current_tickets.keys())
        for ticket in closed_tickets:
            old = self.positions[ticket]
            events.append(TradeEvent(
                master_login=master_login,
                ticket=ticket,
                symbol=old["symbol"],
                action=TradeAction.CLOSE,
                direction=TradeDirection.BUY if old["type"] == 0 else TradeDirection.SELL,
                volume=old["volume"],
                price=old["price_open"],
                sl=old.get("sl", 0.0),
                tp=old.get("tp", 0.0),
                magic_number=old.get("magic", 0),
                detected_at=now,
            ))
            self._sl_tp_cache.pop(ticket, None)

        self.positions = current_tickets
        return events


class OrderHistoryTracker:
    """
    Monitors MT5 order history for faster close detection.
    Closes are detected via deal history before position disappears from positions_get().
    """

    __slots__ = ("_seen_deals",)

    def __init__(self):
        self._seen_deals: Set[int] = set()

    def check_new_deals(self, mt5_module, master_login: int, since_timestamp: int) -> List[TradeEvent]:
        """Check deal history for new entries since last check."""
        events = []
        now = time.time()

        try:
            deals = mt5_module.history_deals_get(since_timestamp, int(time.time()) + 3600)
            if not deals:
                return events

            for deal in deals:
                if deal.ticket in self._seen_deals:
                    continue
                self._seen_deals.add(deal.ticket)

                # deal.entry: 0=IN, 1=OUT, 2=INOUT, 3=OUT_BY
                if deal.entry == 1:  # OUT = close
                    events.append(TradeEvent(
                        master_login=master_login,
                        ticket=deal.position_id,
                        symbol=deal.symbol,
                        action=TradeAction.CLOSE,
                        direction=TradeDirection.BUY if deal.type == 0 else TradeDirection.SELL,
                        volume=deal.volume,
                        price=deal.price,
                        magic_number=deal.magic,
                        detected_at=now,
                    ))
                elif deal.entry == 0:  # IN = open
                    events.append(TradeEvent(
                        master_login=master_login,
                        ticket=deal.position_id,
                        symbol=deal.symbol,
                        action=TradeAction.OPEN,
                        direction=TradeDirection.BUY if deal.type == 0 else TradeDirection.SELL,
                        volume=deal.volume,
                        price=deal.price,
                        sl=0.0,
                        tp=0.0,
                        magic_number=deal.magic,
                        detected_at=now,
                    ))

            # Keep seen deals manageable
            if len(self._seen_deals) > 10000:
                self._seen_deals = set(list(self._seen_deals)[-5000:])

        except Exception as e:
            logger.debug(f"Deal history check error: {e}")

        return events


class MasterListener(threading.Thread):
    """
    Ultra-fast master account listener with continuous 10ms polling.

    Detection pipeline:
      MT5 positions_get() → PositionSnapshot.diff() → Redis publish (pipeline)
                                                         ↓
      MT5 history_deals_get() → OrderHistoryTracker ──→ Redis publish (pipeline)

    Latency budget:
      - MT5 API call:     ~2-5ms
      - Snapshot diff:    ~0.01ms
      - Redis publish:    ~0.1ms (pipeline)
      - Total:            ~5-10ms detection latency
    """

    def __init__(self, master_account_id: str, login: int, password: str, server: str):
        super().__init__(daemon=True, name=f"Listener-{login}")
        self.master_account_id = master_account_id
        self.login = login
        self.password = password
        self.server = server
        self.snapshot = PositionSnapshot()
        self.order_tracker = OrderHistoryTracker()
        self.running = False
        self.redis_client: Optional[redis.Redis] = None
        self._channel = f"{CHANNEL_PREFIX}:{master_account_id}"
        self._queue = f"{QUEUE_PREFIX}:{master_account_id}"
        self._metrics = get_metrics()
        self._poll_count = 0
        self._history_start_ts = int(time.time())

    def connect_mt5(self) -> bool:
        """Initialize MT5 terminal and log in."""
        import MetaTrader5 as mt5
        if not mt5.initialize():
            logger.error(f"[{self.login}] MT5 initialize failed: {mt5.last_error()}")
            return False

        authorized = mt5.login(self.login, password=self.password, server=self.server)
        if not authorized:
            logger.error(f"[{self.login}] MT5 login failed: {mt5.last_error()}")
            mt5.shutdown()
            return False

        info = mt5.account_info()
        if info:
            logger.info(f"[{self.login}] Connected — Balance: {info.balance} Server: {info.server}")
        return True

    def _get_positions_fast(self, mt5_module) -> List[dict]:
        """Fetch positions with minimal overhead."""
        positions = mt5_module.positions_get()
        if not positions:
            return []
        return [
            {
                "ticket": p.ticket,
                "symbol": p.symbol,
                "type": p.type,
                "volume": p.volume,
                "price_open": p.price_open,
                "sl": p.sl,
                "tp": p.tp,
                "magic": p.magic,
            }
            for p in positions
        ]

    def _publish_events(self, events: List[TradeEvent]):
        """Publish events to Redis using pipeline for minimal latency."""
        if not events or not self.redis_client:
            return

        pipe = self.redis_client.pipeline(transaction=False)
        for event in events:
            event.master_account_id = self.master_account_id
            payload = event.to_json()

            # Pub/sub for real-time consumers (distributor)
            pipe.publish(self._channel, payload)
            # List for reliability (persisted queue)
            pipe.lpush(self._queue, payload)
            # Trim queue to prevent unbounded growth
            pipe.ltrim(self._queue, 0, 9999)

            self._metrics.record_event_detected()
            logger.info(
                f"[{self.login}] {event.action.value.upper()} {event.symbol} "
                f"ticket={event.ticket} vol={event.volume} @ {event.price}"
            )

        pipe.execute()

    def run(self):
        """Main ultra-fast polling loop."""
        import MetaTrader5 as mt5

        self.redis_client = redis.Redis.from_url(
            settings.REDIS_URL,
            socket_keepalive=True,
            socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
        )
        self.running = True

        if not self.connect_mt5():
            logger.error(f"[{self.login}] Cannot start listener")
            return

        # Initial snapshot (don't emit events for existing positions)
        initial = self._get_positions_fast(mt5)
        self.snapshot.positions = {p["ticket"]: p for p in initial}
        self.snapshot._sl_tp_cache = {
            p["ticket"]: (p.get("sl", 0.0), p.get("tp", 0.0)) for p in initial
        }
        logger.info(
            f"[{self.login}] Listener started — {len(initial)} positions, "
            f"polling every {settings.MASTER_POLL_INTERVAL_MS}ms"
        )

        poll_interval = settings.MASTER_POLL_INTERVAL_MS / 1000.0
        history_interval = settings.ORDER_HISTORY_POLL_INTERVAL_MS / 1000.0
        last_history_check = time.time()
        seen_event_tickets: Set[int] = set()  # Dedup between position + history

        while self.running:
            loop_start = time.monotonic()

            try:
                # ── 1. Position snapshot diff (primary detection) ──
                current = self._get_positions_fast(mt5)
                events = self.snapshot.diff(current, self.login)

                # ── 2. Order history check (supplemental, less frequent) ──
                now = time.time()
                if settings.LISTENER_USE_ORDERS_HISTORY and (now - last_history_check) >= history_interval:
                    history_events = self.order_tracker.check_new_deals(mt5, self.login, self._history_start_ts)
                    last_history_check = now

                    # Dedup: only add history events not already caught by position diff
                    for he in history_events:
                        if he.ticket not in seen_event_tickets:
                            events.append(he)

                # Track tickets to dedup
                for e in events:
                    seen_event_tickets.add(e.ticket)

                # Keep dedup set manageable
                if len(seen_event_tickets) > 5000:
                    seen_event_tickets = set(list(seen_event_tickets)[-2000:])

                # ── 3. Publish ──
                if events:
                    self._publish_events(events)

                self._poll_count += 1

            except Exception as e:
                logger.error(f"[{self.login}] Poll error: {e}")
                try:
                    mt5.shutdown()
                    time.sleep(0.5)
                    self.connect_mt5()
                except Exception:
                    time.sleep(2)

            # ── Precise sleep to maintain poll interval ──
            elapsed = time.monotonic() - loop_start
            sleep_time = poll_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def stop(self):
        self.running = False
        try:
            import MetaTrader5 as mt5
            mt5.shutdown()
        except Exception:
            pass
        logger.info(f"[{self.login}] Listener stopped (polled {self._poll_count} times)")
