"""MasterMonitor V2 — one process per master.

Polls a master MT5 terminal for new/closed positions and publishes events
to Redis under the V2 namespace ONLY:

  channel: copytrade_v2:events:master:{master_id}
  payload: {
    "event": "OPEN" | "CLOSE",
    "master_id": "...",
    "strategy_id": "...",
    "master_ticket": int,
    "symbol": str,
    "side": "BUY" | "SELL",      # OPEN only
    "volume": float,             # OPEN only
    "price": float,              # OPEN only
    "magic": int,
    "comment": str,
    "ts": float,
  }

V2 isolation:
  * Reads only masters whose engine_version='v2' (via v2_master_flags).
  * Never publishes on V1 channels.
  * Default DRY_RUN: when V2_SESSION_DRY_RUN=true we don't touch MT5 —
    the loop just idles. Real polling runs only when explicitly enabled.

Wiring with executor/distributor lives in `distributor.py` + `main.py`.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from typing import Optional, Set
from uuid import UUID

from .config import get_v2_settings
from .redis_client import publish
from .utils.logger import get_logger


def _dry_run() -> bool:
    val = os.environ.get("V2_SESSION_DRY_RUN", "true").strip().lower()
    return val not in ("0", "false", "no")


@dataclass
class MasterEvent:
    event: str  # OPEN | CLOSE
    master_id: UUID
    strategy_id: UUID
    master_ticket: int
    symbol: str
    side: Optional[str] = None
    volume: Optional[float] = None
    price: Optional[float] = None
    magic: int = 0
    comment: str = ""
    ts: float = 0.0

    def to_payload(self) -> dict:
        return {
            "event": self.event,
            "master_id": str(self.master_id),
            "strategy_id": str(self.strategy_id),
            "master_ticket": self.master_ticket,
            "symbol": self.symbol,
            "side": self.side,
            "volume": self.volume,
            "price": self.price,
            "magic": self.magic,
            "comment": self.comment,
            "ts": self.ts or time.time(),
        }


class MasterMonitor:
    """Per-master polling loop."""

    def __init__(
        self,
        *,
        master_id: UUID,
        strategy_id: UUID,
        terminal_path: str,
        login: int,
        poll_interval_ms: Optional[int] = None,
    ):
        self.master_id = master_id
        self.strategy_id = strategy_id
        self.terminal_path = terminal_path
        self.login = login
        self.settings = get_v2_settings()
        self.poll_interval_ms = poll_interval_ms or self.settings.MASTER_POLL_INTERVAL_MS
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._known: Set[int] = set()
        self.log = get_logger("master_monitor").bind(
            master_id=str(master_id), strategy_id=str(strategy_id),
        )

    # ── lifecycle ─────────────────────────────────────────────────
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, name=f"v2-master-{self.master_id}", daemon=True,
        )
        self._thread.start()
        self.log.info("master monitor started",
                      extra={"action": "master_monitor_started",
                             "dry_run": _dry_run()})

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=timeout)
        self.log.info("master monitor stopped",
                      extra={"action": "master_monitor_stopped"})

    # ── loop ──────────────────────────────────────────────────────
    def _run(self) -> None:
        # In dry-run, don't touch MT5; just idle. This lets the rest of
        # the V2 process boot and run smokes without a real terminal.
        if _dry_run():
            while not self._stop.is_set():
                self._stop.wait(self.poll_interval_ms / 1000.0)
            return

        try:
            import MetaTrader5 as mt5  # type: ignore
        except Exception as e:  # pragma: no cover
            self.log.error("MT5 import failed; monitor idle",
                           extra={"action": "mt5_import_failed"}, exc_info=e)
            return

        # Real init/login is owned by the agent service; we assume the
        # master terminal is already attached for this thread.
        while not self._stop.is_set():
            try:
                # 1) Sync balance/equity every ~1 min
                self._sync_balance_if_needed(mt5)
                # 2) Poll positions
                self._poll_once(mt5)
            except Exception as e:
                self.log.error("poll error",
                               extra={"action": "master_poll_error"}, exc_info=e)
            self._stop.wait(self.poll_interval_ms / 1000.0)

    def _sync_balance_if_needed(self, mt5) -> None:
        now = time.time()
        # Interval from settings or 60s default
        interval = getattr(self.settings, "BALANCE_SYNC_INTERVAL_S", 60)
        if hasattr(self, "_last_balance_sync") and (now - self._last_balance_sync) < interval:
            return

        ai = mt5.account_info()
        if ai:
            from .redis_client import get_redis, k
            r = get_redis()
            # Store in Redis for distributor access
            r.hset(k(f"master:{self.master_id}:stats"), mapping={
                "balance": float(ai.balance),
                "equity": float(ai.equity),
                "updated_at": now
            })
            self._last_balance_sync = now
            self.log.info("master balance synced", 
                         extra={"balance": ai.balance, "equity": ai.equity})

    def _poll_once(self, mt5) -> None:
        positions = mt5.positions_get() or []
        current = {int(p.ticket) for p in positions}

        # OPEN: tickets that are new
        for p in positions:
            t = int(p.ticket)
            if t in self._known:
                continue
            self._known.add(t)
            ev = MasterEvent(
                event="OPEN",
                master_id=self.master_id,
                strategy_id=self.strategy_id,
                master_ticket=t,
                symbol=p.symbol,
                side="BUY" if p.type == mt5.POSITION_TYPE_BUY else "SELL",
                volume=float(p.volume),
                price=float(getattr(p, "price_open", 0.0)),
                magic=int(getattr(p, "magic", 0) or 0),
                comment=str(getattr(p, "comment", "") or ""),
                ts=time.time(),
            )
            self._publish(ev)

        # CLOSE: tickets that disappeared
        gone = self._known - current
        for t in gone:
            self._known.discard(t)
            ev = MasterEvent(
                event="CLOSE",
                master_id=self.master_id,
                strategy_id=self.strategy_id,
                master_ticket=t,
                symbol="",  # unknown post-close; consumers use master_ticket
                ts=time.time(),
            )
            self._publish(ev)

    def _publish(self, ev: MasterEvent) -> None:
        channel = f"events:master:{self.master_id}"
        n = publish(channel, ev.to_payload())
        self.log.info(
            f"master event published: {ev.event}",
            extra={
                "action": "master_event_published",
                "event": ev.event,
                "master_ticket": ev.master_ticket,
                "symbol": ev.symbol,
                "subscribers": n,
            },
        )
