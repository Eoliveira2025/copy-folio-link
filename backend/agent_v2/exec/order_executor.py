"""OrderExecutor — real `mt5.order_send` for V2 (OPEN + CLOSE only).

Designed to be plugged into ExecutionQueue as the task handler:

    executor = OrderExecutor(pool_id=..., terminal_id=..., pool_name=...)
    queue = ExecutionQueue(..., handler=executor)

Pre-flight (in order):
  1. circuit breaker  → ExecutionError("CIRCUIT_OPEN") if tripped
  2. rate limit       → ExecutionError("RATE_LIMITED") if bucket empty
  3. safety guard     → re-checked here defensively (queue checks too)
  4. terminal_info()  → must be present
  5. account_info()   → login must match
  6. symbol_select(symbol, True)
  7. tick bid/ask     → both > 0
  8. volume vs symbol_info (volume_min/max/step)

OPEN  → mt5.order_send(TRADE_ACTION_DEAL with BUY/SELL)
CLOSE → fetch position by `client_ticket` ONLY, then opposite-side DEAL
        with `position=client_ticket`. Never matched by symbol/volume.
MODIFY → not implemented in this increment.

DRY_RUN behaviour:
  This handler is a no-op simulator when called by the queue while the
  safety guard returns simulate_only=True; the queue handles that path
  before reaching us. We still defensively check `can_execute_order`.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any, Optional
from uuid import UUID

from ..config import get_v2_settings
from ..utils.logger import get_logger
from .order_task import OrderAction, OrderSide, OrderTask
from .safety_guard import can_execute_order
from .circuit_breaker import CircuitBreaker
from .rate_limiter import TokenBucket


class ExecutionError(RuntimeError):
    """Raised when pre-flight or order_send fails."""

    def __init__(self, code: str, message: str = ""):
        super().__init__(f"{code}: {message}" if message else code)
        self.code = code


@dataclass
class ExecutionResult:
    retcode: int
    broker_comment: str
    order_latency_ms: float
    deal_ticket: Optional[int] = None
    order_ticket: Optional[int] = None
    price: Optional[float] = None
    volume: Optional[float] = None


def _safe_import_mt5():
    try:
        import MetaTrader5 as mt5  # type: ignore
        return mt5
    except Exception as e:
        raise ExecutionError("MT5_IMPORT_FAILED", str(e))


def _round_volume(vol: float, step: float, vmin: float, vmax: float) -> float:
    if step <= 0:
        step = 0.01
    n = math.floor(vol / step + 1e-9)
    v = max(vmin, min(vmax, n * step))
    # Avoid float drift like 0.30000000004
    return round(v, 8)


class OrderExecutor:
    """Per-pool real executor. One instance per (pool_id, terminal_id)."""

    def __init__(
        self,
        *,
        pool_id: UUID,
        terminal_id: UUID,
        pool_name: str,
        master_id: UUID,
        strategy_id: UUID,
        on_circuit_trip=None,
        deviation_points: Optional[int] = None,
    ):
        self.pool_id = pool_id
        self.terminal_id = terminal_id
        self.pool_name = pool_name
        self.master_id = master_id
        self.strategy_id = strategy_id
        self.settings = get_v2_settings()
        self.deviation = (
            deviation_points
            if deviation_points is not None
            else self.settings.MAX_SLIPPAGE_POINTS
        )
        self.cb = CircuitBreaker(
            pool_id=pool_id, pool_name=pool_name, on_trip=on_circuit_trip,
        )
        self.bucket = TokenBucket(
            rate_per_s=self.settings.POOL_RATE_LIMIT_PER_S,
            burst=self.settings.POOL_RATE_LIMIT_BURST,
        )
        self.log = get_logger("executor").bind(
            pool_id=str(pool_id), pool_name=pool_name,
            terminal_id=str(terminal_id),
            master_id=str(master_id), strategy_id=str(strategy_id),
        )

    # Plug as ExecutionQueue handler: callable returns retcode-like int
    def __call__(self, task: OrderTask, session_info: dict) -> int:
        result = self.execute(task, session_info)
        return result.retcode

    # ── public ────────────────────────────────────────────────────
    def execute(self, task: OrderTask, session_info: dict) -> ExecutionResult:
        log = self.log.bind(**task.log_fields())

        # 1) circuit breaker
        if self.cb.is_open():
            self._record_metrics(log, task, retcode=-1, comment="CIRCUIT_OPEN",
                                 order_latency_ms=0.0,
                                 login_latency_ms=session_info.get("login_latency_ms", 0.0))
            raise ExecutionError("CIRCUIT_OPEN", f"pool {self.pool_name} disabled")

        # 2) rate limit
        if not self.bucket.try_acquire(1.0):
            self._record_metrics(log, task, retcode=-2, comment="RATE_LIMITED",
                                 order_latency_ms=0.0,
                                 login_latency_ms=session_info.get("login_latency_ms", 0.0))
            raise ExecutionError("RATE_LIMITED", f"pool {self.pool_name}")

        # 3) safety guard (defensive double-check)
        # account_type is unknown at this layer; trust queue's earlier
        # check unless caller injected it via session_info.
        atype = session_info.get("account_type", "demo")
        login = session_info.get("login", 0)
        decision = can_execute_order(task.account_id, login, atype)
        if not decision.allowed:
            raise ExecutionError("BLOCKED_BY_SAFETY",
                                 decision.reason_if_blocked or "blocked")

        mt5 = _safe_import_mt5()

        # 4) terminal_info / account_info
        ti = mt5.terminal_info()
        if ti is None:
            self._fail("NO_TERMINAL_INFO", log, task, session_info)
        ai = mt5.account_info()
        if ai is None:
            self._fail("NO_ACCOUNT_INFO", log, task, session_info)
        if login and getattr(ai, "login", None) and int(ai.login) != int(login):
            self._fail(
                f"LOGIN_MISMATCH:expected={login},got={ai.login}",
                log, task, session_info,
            )

        # 5) symbol_select + tick
        if not mt5.symbol_select(task.symbol, True):
            self._fail(f"SYMBOL_SELECT_FAILED:{task.symbol}", log, task, session_info)
        sym = mt5.symbol_info(task.symbol)
        if sym is None:
            self._fail(f"SYMBOL_INFO_NONE:{task.symbol}", log, task, session_info)
        tick = mt5.symbol_info_tick(task.symbol)
        if tick is None or not tick.bid or not tick.ask:
            self._fail(f"BAD_TICK:{task.symbol}", log, task, session_info)

        if task.action == OrderAction.OPEN:
            return self._do_open(mt5, sym, tick, task, session_info, log)
        if task.action == OrderAction.CLOSE:
            return self._do_close(mt5, sym, tick, task, session_info, log)
        if task.action == OrderAction.MODIFY:
            raise ExecutionError("MODIFY_NOT_IMPLEMENTED",
                                 "MODIFY lands in a later increment")
        raise ExecutionError("UNKNOWN_ACTION", str(task.action))

    # ── OPEN ──────────────────────────────────────────────────────
    def _do_open(self, mt5, sym, tick, task: OrderTask,
                 session_info: dict, log) -> ExecutionResult:
        if not task.side or task.volume is None:
            self._fail("OPEN_MISSING_FIELDS", log, task, session_info)

        vol = _round_volume(
            float(task.volume), sym.volume_step, sym.volume_min, sym.volume_max
        )
        if vol < sym.volume_min or vol > sym.volume_max or vol <= 0:
            self._fail(
                f"BAD_VOLUME:{task.volume}->{vol},min={sym.volume_min},"
                f"max={sym.volume_max},step={sym.volume_step}",
                log, task, session_info,
            )

        is_buy = task.side == OrderSide.BUY
        price = tick.ask if is_buy else tick.bid

        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": task.symbol,
            "volume": vol,
            "type": mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL,
            "price": price,
            "deviation": int(self.deviation),
            "magic": int(task.magic or 0),
            "comment": (task.comment or f"v2:{task.idempotency_key}")[:31],
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        if task.sl is not None:
            req["sl"] = float(task.sl)
        if task.tp is not None:
            req["tp"] = float(task.tp)

        return self._send(mt5, req, task, session_info, log)

    # ── CLOSE (by client_ticket ONLY) ─────────────────────────────
    def _do_close(self, mt5, sym, tick, task: OrderTask,
                  session_info: dict, log) -> ExecutionResult:
        if not task.client_ticket:
            self._fail("CLOSE_REQUIRES_CLIENT_TICKET", log, task, session_info)

        positions = mt5.positions_get(ticket=int(task.client_ticket))
        if not positions:
            self._fail(
                f"POSITION_NOT_FOUND:client_ticket={task.client_ticket}",
                log, task, session_info,
            )
        pos = positions[0]
        if pos.symbol != task.symbol:
            # Defensive: never fall back to symbol-based matching.
            self._fail(
                f"POSITION_SYMBOL_MISMATCH:expected={task.symbol},"
                f"got={pos.symbol},ticket={task.client_ticket}",
                log, task, session_info,
            )

        # Opposite side; price taken from current tick on the close side.
        is_buy_close = pos.type == mt5.POSITION_TYPE_SELL
        price = tick.ask if is_buy_close else tick.bid

        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": pos.symbol,
            "volume": float(pos.volume),
            "type": mt5.ORDER_TYPE_BUY if is_buy_close else mt5.ORDER_TYPE_SELL,
            "position": int(pos.ticket),  # close THIS ticket only
            "price": price,
            "deviation": int(self.deviation),
            "magic": int(pos.magic or task.magic or 0),
            "comment": (task.comment or f"v2:close:{pos.ticket}")[:31],
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        return self._send(mt5, req, task, session_info, log)

    # ── transport ─────────────────────────────────────────────────
    def _send(self, mt5, req: dict, task: OrderTask,
              session_info: dict, log) -> ExecutionResult:
        t0 = time.monotonic()
        res = mt5.order_send(req)
        latency_ms = (time.monotonic() - t0) * 1000.0

        if res is None:
            err = mt5.last_error()
            comment = f"order_send_returned_none:{err}"
            self.cb.record_failure(comment)
            self._record_metrics(log, task, retcode=-3, comment=comment,
                                 order_latency_ms=latency_ms,
                                 login_latency_ms=session_info.get(
                                     "login_latency_ms", 0.0))
            raise ExecutionError("ORDER_SEND_NONE", comment)

        retcode = int(res.retcode)
        comment = str(getattr(res, "comment", "") or "")
        ok = retcode == mt5.TRADE_RETCODE_DONE
        if ok:
            self.cb.record_success()
        else:
            self.cb.record_failure(f"retcode={retcode}:{comment}")

        result = ExecutionResult(
            retcode=retcode,
            broker_comment=comment,
            order_latency_ms=latency_ms,
            deal_ticket=int(getattr(res, "deal", 0)) or None,
            order_ticket=int(getattr(res, "order", 0)) or None,
            price=float(getattr(res, "price", 0.0)) or None,
            volume=float(getattr(res, "volume", 0.0)) or None,
        )
        self._record_metrics(
            log, task, retcode=retcode, comment=comment,
            order_latency_ms=latency_ms,
            login_latency_ms=session_info.get("login_latency_ms", 0.0),
            deal_ticket=result.deal_ticket, order_ticket=result.order_ticket,
        )
        if not ok:
            raise ExecutionError(f"RETCODE_{retcode}", comment)
        return result

    # ── helpers ───────────────────────────────────────────────────
    def _fail(self, reason: str, log, task: OrderTask, session_info: dict):
        self.cb.record_failure(reason)
        self._record_metrics(
            log, task, retcode=-4, comment=reason, order_latency_ms=0.0,
            login_latency_ms=session_info.get("login_latency_ms", 0.0),
        )
        raise ExecutionError("PREFLIGHT_FAILED", reason)

    def _record_metrics(
        self,
        log,
        task: OrderTask,
        *,
        retcode: int,
        comment: str,
        order_latency_ms: float,
        login_latency_ms: float,
        deal_ticket: Optional[int] = None,
        order_ticket: Optional[int] = None,
    ) -> None:
        log.info(
            "order_send result",
            extra={
                "action": "order_send_result",
                "retcode": retcode,
                "broker_comment": comment,
                "order_latency_ms": round(order_latency_ms, 2),
                "login_latency_ms": round(login_latency_ms, 2),
                "pool_id": str(self.pool_id),
                "terminal_id": str(self.terminal_id),
                "account_id": str(task.account_id),
                "strategy_id": str(self.strategy_id),
                "master_id": str(self.master_id),
                "deal_ticket": deal_ticket,
                "order_ticket": order_ticket,
                "circuit_open": self.cb.is_open(),
            },
        )
