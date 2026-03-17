"""
Master Account Monitor — connects to master MT5 accounts and detects trades.

Each master runs in its own subprocess (MT5 API limitation: one login per process).
Publishes TradeEvents to Redis for the Distributor to consume.
"""

from __future__ import annotations
import time
import logging
import multiprocessing
from typing import Dict, List, Optional, Set
import redis
import MetaTrader5 as mt5

from agent.config import get_agent_settings

settings = get_agent_settings()
logger = logging.getLogger("agent.master_monitor")

CHANNEL_PREFIX = "copytrade:events"
QUEUE_PREFIX = "copytrade:queue"


try:
    import orjson
    def _dumps(d: dict) -> str:
        return orjson.dumps(d).decode()
except ImportError:
    import json
    _dumps = json.dumps


class PositionSnapshot:
    """Fast position differ using dict lookup."""

    __slots__ = ("positions", "_sl_tp_cache")

    def __init__(self):
        self.positions: Dict[int, dict] = {}
        self._sl_tp_cache: Dict[int, tuple] = {}

    def diff(self, current_positions: List[dict], master_login: int) -> List[dict]:
        """Compare current vs previous snapshot. Returns event dicts."""
        events = []
        current_tickets: Dict[int, dict] = {}
        now = time.time()

        for pos in current_positions:
            ticket = pos["ticket"]
            current_tickets[ticket] = pos

            if ticket not in self.positions:
                # NEW POSITION
                events.append({
                    "master_login": master_login,
                    "ticket": ticket,
                    "symbol": pos["symbol"],
                    "action": "open",
                    "direction": "BUY" if pos["type"] == 0 else "SELL",
                    "volume": pos["volume"],
                    "price": pos["price_open"],
                    "sl": pos.get("sl", 0.0),
                    "tp": pos.get("tp", 0.0),
                    "magic_number": pos.get("magic", 0),
                    "detected_at": now,
                })
            else:
                # CHECK MODIFY (SL/TP change)
                cached = self._sl_tp_cache.get(ticket)
                new_sl_tp = (pos.get("sl", 0.0), pos.get("tp", 0.0))
                if cached and cached != new_sl_tp:
                    events.append({
                        "master_login": master_login,
                        "ticket": ticket,
                        "symbol": pos["symbol"],
                        "action": "modify",
                        "direction": "BUY" if pos["type"] == 0 else "SELL",
                        "volume": pos["volume"],
                        "price": pos["price_open"],
                        "sl": new_sl_tp[0],
                        "tp": new_sl_tp[1],
                        "magic_number": pos.get("magic", 0),
                        "detected_at": now,
                    })

            self._sl_tp_cache[ticket] = (pos.get("sl", 0.0), pos.get("tp", 0.0))

        # CLOSED POSITIONS
        closed_tickets = set(self.positions.keys()) - set(current_tickets.keys())
        for ticket in closed_tickets:
            old = self.positions[ticket]
            events.append({
                "master_login": master_login,
                "ticket": ticket,
                "symbol": old["symbol"],
                "action": "close",
                "direction": "BUY" if old["type"] == 0 else "SELL",
                "volume": old["volume"],
                "price": old["price_open"],
                "sl": old.get("sl", 0.0),
                "tp": old.get("tp", 0.0),
                "magic_number": old.get("magic", 0),
                "detected_at": now,
            })
            self._sl_tp_cache.pop(ticket, None)

        self.positions = current_tickets
        return events


def master_listener_process(master_id: str, login: int, password: str, server: str,
                            instance_path: str = ""):
    """
    Subprocess entry point: connects to a master MT5 account using
    a DEDICATED terminal instance (separate folder per account).

    Args:
        instance_path: Full path to terminal64.exe in the account's own MT5 folder.
                       If empty, falls back to settings.MT5_TERMINAL_PATH.
    """
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format=f"%(asctime)s.%(msecs)03d [Master-{login}] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    log = logging.getLogger(f"master.{login}")

    terminal_path = instance_path or settings.MT5_TERMINAL_PATH
    log.info(f"Initializing MT5 with dedicated instance: {terminal_path}")

    # Connect to MT5 — pass credentials directly to initialize()
    # Each account uses its OWN terminal64.exe in its OWN folder
    if not mt5.initialize(
        path=terminal_path,
        login=login,
        password=password,
        server=server,
        timeout=settings.MT5_INIT_TIMEOUT_MS,
        portable=True,
    ):
        log.error(f"MT5 initialize failed: {mt5.last_error()}")
        return

    info = mt5.account_info()
    if info:
        log.info(f"Connected — Balance: {info.balance}, Server: {info.server}")

    # Connect to Redis
    redis_client = redis.Redis.from_url(
        settings.REDIS_URL,
        socket_keepalive=True,
        socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
    )

    channel = f"{CHANNEL_PREFIX}:{master_id}"
    queue = f"{QUEUE_PREFIX}:{master_id}"

    snapshot = PositionSnapshot()
    poll_interval = settings.MASTER_POLL_INTERVAL_MS / 1000.0

    # Initial snapshot — don't emit events for existing positions
    positions = mt5.positions_get()
    if positions:
        initial = [
            {"ticket": p.ticket, "symbol": p.symbol, "type": p.type,
             "volume": p.volume, "price_open": p.price_open,
             "sl": p.sl, "tp": p.tp, "magic": p.magic}
            for p in positions
        ]
        snapshot.positions = {p["ticket"]: p for p in initial}
        snapshot._sl_tp_cache = {p["ticket"]: (p["sl"], p["tp"]) for p in initial}
        log.info(f"Initial snapshot: {len(initial)} positions")

    # Publish master balance to Redis for the distributor
    if info:
        redis_client.set(f"copytrade:master_balance:{master_id}", str(info.balance), ex=120)

    poll_count = 0
    balance_sync_counter = 0

    while True:
        loop_start = time.monotonic()

        try:
            # Get current positions
            positions = mt5.positions_get()
            current = []
            if positions:
                current = [
                    {"ticket": p.ticket, "symbol": p.symbol, "type": p.type,
                     "volume": p.volume, "price_open": p.price_open,
                     "sl": p.sl, "tp": p.tp, "magic": p.magic}
                    for p in positions
                ]

            # Diff
            events = snapshot.diff(current, login)

            # Publish events
            if events:
                pipe = redis_client.pipeline(transaction=False)
                for event in events:
                    event["master_account_id"] = master_id
                    import uuid
                    event["event_id"] = uuid.uuid4().hex
                    payload = _dumps(event)
                    pipe.publish(channel, payload)
                    pipe.lpush(queue, payload)
                    pipe.ltrim(queue, 0, 9999)

                    log.info(
                        f"{event['action'].upper()} {event['symbol']} "
                        f"ticket={event['ticket']} vol={event['volume']} @ {event['price']}"
                    )
                pipe.execute()

            # Periodic balance sync (every ~60s)
            balance_sync_counter += 1
            if balance_sync_counter >= int(settings.BALANCE_SYNC_INTERVAL_S / max(poll_interval, 0.01)):
                balance_sync_counter = 0
                acc_info = mt5.account_info()
                if acc_info:
                    redis_client.set(
                        f"copytrade:master_balance:{master_id}",
                        str(acc_info.balance), ex=120,
                    )

            poll_count += 1

        except redis.ConnectionError:
            log.error("Redis connection lost, reconnecting...")
            time.sleep(2)
            try:
                redis_client = redis.Redis.from_url(settings.REDIS_URL)
            except Exception:
                pass
        except Exception as e:
            log.error(f"Poll error: {e}", exc_info=True)
            # Try to reconnect MT5 using the SAME dedicated instance
            try:
                mt5.shutdown()
                time.sleep(1)
                mt5.initialize(
                    path=terminal_path,
                    login=login,
                    password=password,
                    server=server,
                    timeout=settings.MT5_INIT_TIMEOUT_MS,
                    portable=True,
                )
            except Exception:
                time.sleep(5)

        # Precise sleep
        elapsed = time.monotonic() - loop_start
        sleep_time = poll_interval - elapsed
        if sleep_time > 0:
            time.sleep(sleep_time)
