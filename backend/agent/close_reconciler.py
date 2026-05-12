"""
Close Reconciler — defensive verifier for client position closes.

Runs as a background thread INSIDE each executor subprocess (so it shares
the MT5 connection of that client account). After every CLOSE attempt
the executor enqueues a verification task. The reconciler periodically:

  1. Looks up the matching client position (by client_ticket if known,
     otherwise by symbol + exact comment "CT:{master_ticket}" + magic).
  2. If the position no longer exists -> JA_NAO_EXISTE (OK, manual close
     accepted when CLOSE_RECONCILER_ACCEPT_MANUAL_CLOSE=true).
  3. If it still exists -> retry close at current market price (BID for
     BUY positions, ASK for SELL), tolerant to slippage / requote /
     off-quotes / terminal busy.
  4. After CLOSE_RECONCILER_MAX_ATTEMPTS unsuccessful retries, marks
     FALHOU_APOS_TENTATIVAS and stops.

Safety invariants (do not change without review):
  * Never touches positions that do not match the master_ticket mapping
    or the exact "CT:{master_ticket}" comment.
  * Never enqueues a task twice for the same master_ticket while one is
    already pending (in-memory dedup).
  * Never raises out of the worker loop.
  * Never alters open/lot/distributor/master logic.

Activation:
  Controlled by settings.CLOSE_RECONCILER_ENABLED (default False).
  When false, enqueue() is a no-op and the thread is not started.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import MetaTrader5 as mt5

from agent.config import get_agent_settings

settings = get_agent_settings()


# MT5 retcodes that mean "transient — retry later"
_TRANSIENT_RETCODES = {
    getattr(mt5, "TRADE_RETCODE_REQUOTE", 10004),
    getattr(mt5, "TRADE_RETCODE_PRICE_OFF", 10021),
    getattr(mt5, "TRADE_RETCODE_PRICE_CHANGED", 10020),
    getattr(mt5, "TRADE_RETCODE_TIMEOUT", 10008),
    getattr(mt5, "TRADE_RETCODE_REJECT", 10006),
    getattr(mt5, "TRADE_RETCODE_ERROR", 10011),
    getattr(mt5, "TRADE_RETCODE_CONNECTION", 10031),
    getattr(mt5, "TRADE_RETCODE_TRADE_DISABLED", 10017),
    getattr(mt5, "TRADE_RETCODE_MARKET_CLOSED", 10018),
    getattr(mt5, "TRADE_RETCODE_NO_MONEY", 10019),
    getattr(mt5, "TRADE_RETCODE_TOO_MANY_REQUESTS", 10030),
}

# MT5 retcodes that mean "position no longer exists"
_GONE_RETCODES = {
    getattr(mt5, "TRADE_RETCODE_POSITION_CLOSED", 10039),
    getattr(mt5, "TRADE_RETCODE_INVALID_FILL", 10030),
}


def _parse_delays(raw: str) -> List[float]:
    out: List[float] = []
    for part in (raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(float(part))
        except ValueError:
            continue
    return out or [2.0, 5.0, 10.0, 20.0, 30.0]


@dataclass
class _Task:
    master_ticket: int
    symbol: str
    magic: int
    client_ticket: Optional[int]
    attempts_done: int = 0
    next_attempt_at: float = 0.0
    extra: dict = field(default_factory=dict)


class CloseReconciler(threading.Thread):
    """In-process close verifier. One per executor subprocess."""

    def __init__(self, client_id: str, log: logging.Logger,
                 ticket_map: Dict[int, int]):
        super().__init__(daemon=True, name=f"CloseReconciler-{client_id}")
        self.client_id = client_id
        self.log = log
        self.ticket_map = ticket_map  # shared reference with executor
        self._lock = threading.Lock()
        self._tasks: Dict[int, _Task] = {}  # master_ticket -> task
        self._stop = threading.Event()
        self._delays = _parse_delays(settings.CLOSE_RECONCILER_RETRY_DELAYS_SECONDS)
        self._max_attempts = max(1, int(settings.CLOSE_RECONCILER_MAX_ATTEMPTS))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def enqueue(self, order: dict) -> None:
        """Schedule (or refresh) a verification for this close order.

        Idempotent: if a task already exists for the same master_ticket,
        we do NOT add a duplicate — preventing double-close attempts.
        """
        if not settings.CLOSE_RECONCILER_ENABLED:
            return
        try:
            master_ticket = int(order.get("master_ticket") or 0)
        except (TypeError, ValueError):
            master_ticket = 0
        if master_ticket <= 0:
            return
        symbol = order.get("symbol") or ""
        if not symbol:
            return

        client_ticket = self.ticket_map.get(master_ticket)
        magic = int(order.get("magic_number") or 0)

        with self._lock:
            if master_ticket in self._tasks:
                # already being reconciled — do nothing (avoid duplicates)
                return
            self._tasks[master_ticket] = _Task(
                master_ticket=master_ticket,
                symbol=symbol,
                magic=magic,
                client_ticket=client_ticket,
                attempts_done=0,
                next_attempt_at=time.time() + self._delays[0],
            )
        self.log.info(
            f"[reconciler] enqueued master={master_ticket} symbol={symbol} "
            f"client_ticket={client_ticket} magic={magic}"
        )

    def stop(self) -> None:
        self._stop.set()

    # ------------------------------------------------------------------
    # Worker loop
    # ------------------------------------------------------------------
    def run(self) -> None:
        self.log.info(
            f"[reconciler] started (max_attempts={self._max_attempts}, "
            f"delays={self._delays}, accept_manual_close="
            f"{settings.CLOSE_RECONCILER_ACCEPT_MANUAL_CLOSE})"
        )
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception as e:
                self.log.error(f"[reconciler] loop error: {e}", exc_info=True)
            self._stop.wait(1.0)

    def _tick(self) -> None:
        now = time.time()
        with self._lock:
            due = [t for t in self._tasks.values() if t.next_attempt_at <= now]
        for task in due:
            self._process(task)

    # ------------------------------------------------------------------
    # Per-task processing
    # ------------------------------------------------------------------
    def _find_position(self, task: _Task):
        """Return the matching position object, or None if not found.

        Strict matching: prefers client_ticket; otherwise requires
        symbol + exact comment "CT:{master_ticket}" + magic match.
        Never returns a position that does not satisfy these checks.
        """
        try:
            if task.client_ticket:
                positions = mt5.positions_get(ticket=task.client_ticket)
                if positions:
                    pos = positions[0]
                    if pos.symbol == task.symbol:
                        return pos
                # client_ticket lookup failed — fall through to comment match
            positions = mt5.positions_get(symbol=task.symbol) or []
            wanted_comment = f"CT:{task.master_ticket}"
            for pos in positions:
                if (pos.comment or "") == wanted_comment and (
                    task.magic == 0 or pos.magic == task.magic
                ):
                    return pos
        except Exception as e:
            self.log.error(f"[reconciler] positions_get error: {e}")
        return None

    def _process(self, task: _Task) -> None:
        master_ticket = task.master_ticket

        position = self._find_position(task)
        if position is None:
            # JA_NAO_EXISTE — manual close or previous close confirmed
            status = "JA_NAO_EXISTE" if settings.CLOSE_RECONCILER_ACCEPT_MANUAL_CLOSE else "OK"
            self.log.info(
                f"[reconciler] master={master_ticket} {status} "
                f"(no matching position) — done"
            )
            self._remove(master_ticket)
            self.ticket_map.pop(master_ticket, None)
            return

        # Position still exists — try to close it at market.
        task.attempts_done += 1
        ok, retcode, comment = self._try_close(position, task)

        if ok:
            self.log.info(
                f"[reconciler] master={master_ticket} FECHADO_OK "
                f"client_ticket={position.ticket} attempt={task.attempts_done}"
            )
            self._remove(master_ticket)
            self.ticket_map.pop(master_ticket, None)
            return

        if retcode in _GONE_RETCODES:
            self.log.info(
                f"[reconciler] master={master_ticket} JA_NAO_EXISTE "
                f"(retcode {retcode}: {comment})"
            )
            self._remove(master_ticket)
            self.ticket_map.pop(master_ticket, None)
            return

        # Failed but transient (or unknown) — schedule retry if budget left
        if task.attempts_done >= self._max_attempts:
            self.log.error(
                f"[reconciler] master={master_ticket} FALHOU_APOS_TENTATIVAS "
                f"attempts={task.attempts_done} last_retcode={retcode} "
                f"comment={comment}"
            )
            self._remove(master_ticket)
            return

        delay_idx = min(task.attempts_done, len(self._delays) - 1)
        delay = self._delays[delay_idx]
        with self._lock:
            task.next_attempt_at = time.time() + delay
        self.log.warning(
            f"[reconciler] master={master_ticket} retry "
            f"{task.attempts_done}/{self._max_attempts} in {delay:.0f}s "
            f"(retcode={retcode}, {comment})"
        )

    def _try_close(self, position, task: _Task):
        """Send a market close for this exact position. Returns (ok, retcode, comment)."""
        symbol = task.symbol
        # Defensive: ensure symbol is selected in Market Watch
        try:
            info = mt5.symbol_info(symbol)
            if info is None or not getattr(info, "visible", False):
                mt5.symbol_select(symbol, True)
        except Exception as e:
            self.log.error(f"[reconciler] symbol_select error {symbol}: {e}")

        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            return False, -1, "no tick"

        # BUY position -> close with SELL at BID; SELL position -> close with BUY at ASK
        if position.type == mt5.POSITION_TYPE_BUY:
            close_type = mt5.ORDER_TYPE_SELL
            price = tick.bid
        else:
            close_type = mt5.ORDER_TYPE_BUY
            price = tick.ask

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": position.volume,
            "type": close_type,
            "position": position.ticket,
            "price": price,
            # Generous deviation: accept best available market price
            "deviation": max(int(settings.MAX_SLIPPAGE_POINTS), 100),
            "magic": position.magic or task.magic or 123456,
            "comment": f"CT:reconcile:{task.master_ticket}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        try:
            result = mt5.order_send(request)
        except Exception as e:
            return False, -1, f"order_send raised: {e}"

        if result is None:
            return False, -1, f"no response ({mt5.last_error()})"
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            return True, result.retcode, result.comment or "ok"
        return False, result.retcode, result.comment or ""

    def _remove(self, master_ticket: int) -> None:
        with self._lock:
            self._tasks.pop(master_ticket, None)
