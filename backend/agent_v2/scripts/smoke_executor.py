"""Smoke test for OrderExecutor.

NO real MT5 and NO real account. We inject a fake `MetaTrader5` module
into sys.modules and exercise:

  * DRY_RUN mode: queue path uses simulator, `mt5.order_send` is NOT
    called (verified by counter on fake module).
  * DEMO_ONLY + ORDER_EXECUTION_ENABLED=true + demo whitelist:
      - OPEN succeeds (TRADE_RETCODE_DONE)
      - CLOSE by client_ticket succeeds and uses position=ticket
      - CLOSE missing client_ticket fails fast
      - CLOSE with wrong symbol vs position fails (no symbol fallback)
      - 5 consecutive failures trip the circuit breaker (next call blocked)
      - rate limiter: bucket=2 → 3rd call within burst window is RATE_LIMITED
"""

from __future__ import annotations

import os
import sys
import types
from uuid import UUID, uuid4

# Reset env before settings are cached
os.environ["V2_EXECUTION_MODE"] = "DRY_RUN"
os.environ["V2_ORDER_EXECUTION_ENABLED"] = "false"
os.environ["V2_POOL_CB_FAILURE_THRESHOLD"] = "5"
os.environ["V2_POOL_RATE_LIMIT_PER_S"] = "0"   # no refill
os.environ["V2_POOL_RATE_LIMIT_BURST"] = "100"  # high enough for normal tests
os.environ["V2_SESSION_DRY_RUN"] = "true"

from agent_v2.config import get_v2_settings  # noqa: E402
get_v2_settings.cache_clear()


# ─────────────────────────────────────────────────────────────────
# Fake MetaTrader5 module
# ─────────────────────────────────────────────────────────────────
class _Tick:
    def __init__(self, bid=1.1000, ask=1.1002):
        self.bid, self.ask = bid, ask


class _Sym:
    def __init__(self):
        self.volume_min = 0.01
        self.volume_max = 100.0
        self.volume_step = 0.01


class _TI:
    connected = True
    trade_allowed = True


class _AI:
    def __init__(self, login=12345678):
        self.login = login


class _Pos:
    def __init__(self, ticket, symbol="EURUSD", volume=0.10, side=0, magic=99):
        self.ticket = ticket
        self.symbol = symbol
        self.volume = volume
        self.type = side  # 0=BUY, 1=SELL
        self.magic = magic


class _Res:
    def __init__(self, retcode, comment="ok", deal=1, order=2, price=1.1, volume=0.1):
        self.retcode = retcode
        self.comment = comment
        self.deal = deal
        self.order = order
        self.price = price
        self.volume = volume


def _build_fake_mt5(*, login=12345678, force_retcode=None):
    m = types.SimpleNamespace()
    # constants
    m.TRADE_ACTION_DEAL = 1
    m.ORDER_TYPE_BUY = 0
    m.ORDER_TYPE_SELL = 1
    m.POSITION_TYPE_BUY = 0
    m.POSITION_TYPE_SELL = 1
    m.ORDER_TIME_GTC = 0
    m.ORDER_FILLING_IOC = 1
    m.TRADE_RETCODE_DONE = 10009

    # state
    m._positions: dict[int, _Pos] = {}
    m.send_count = 0
    m.last_request = None

    def initialize(**kw): return True
    def shutdown(): return True
    def last_error(): return (1, "fake_err")
    def terminal_info(): return _TI()
    def account_info(): return _AI(login)
    def symbol_select(s, on=True): return True
    def symbol_info(s): return _Sym()
    def symbol_info_tick(s): return _Tick()
    def positions_get(ticket=None, symbol=None):
        if ticket and ticket in m._positions:
            return [m._positions[ticket]]
        return []

    def order_send(req):
        m.send_count += 1
        m.last_request = req
        rc = force_retcode if force_retcode is not None else m.TRADE_RETCODE_DONE
        return _Res(retcode=rc, comment="forced" if force_retcode else "ok")

    m.initialize = initialize
    m.shutdown = shutdown
    m.last_error = last_error
    m.terminal_info = terminal_info
    m.account_info = account_info
    m.symbol_select = symbol_select
    m.symbol_info = symbol_info
    m.symbol_info_tick = symbol_info_tick
    m.positions_get = positions_get
    m.order_send = order_send
    return m


def _install_fake_mt5(mt5):
    sys.modules["MetaTrader5"] = mt5


# ─────────────────────────────────────────────────────────────────
# Test helpers
# ─────────────────────────────────────────────────────────────────
from agent_v2.exec.order_task import OrderAction, OrderSide, OrderTask  # noqa: E402
from agent_v2.exec.order_executor import (  # noqa: E402
    OrderExecutor, ExecutionError,
)


def _mk_task(action, *, account_id, symbol="EURUSD",
             side=OrderSide.BUY, volume=0.10, client_ticket=None):
    return OrderTask(
        account_id=account_id,
        pool_id=uuid4(),
        terminal_id=uuid4(),
        master_id=uuid4(),
        strategy_id=uuid4(),
        action=action,
        symbol=symbol,
        side=side if action == OrderAction.OPEN else None,
        volume=volume if action == OrderAction.OPEN else None,
        client_ticket=client_ticket,
        magic=42,
    )


def _mk_executor():
    return OrderExecutor(
        pool_id=uuid4(), terminal_id=uuid4(), pool_name="pool_demo_01",
        master_id=uuid4(), strategy_id=uuid4(),
    )


def _session(login=12345678, account_type="demo"):
    return {"login_latency_ms": 12.3, "switched": True,
            "login": login, "account_type": account_type}


# ─────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────
def test_dry_run_blocks_real_order_send():
    """In DRY_RUN, executor's safety guard MUST block order_send."""
    os.environ["V2_EXECUTION_MODE"] = "DRY_RUN"
    os.environ["V2_ORDER_EXECUTION_ENABLED"] = "false"
    get_v2_settings.cache_clear()

    mt5 = _build_fake_mt5()
    _install_fake_mt5(mt5)
    ex = _mk_executor()
    aid = uuid4()
    try:
        ex.execute(_mk_task(OrderAction.OPEN, account_id=aid),
                   _session(account_type="demo"))
    except ExecutionError as e:
        assert e.code == "BLOCKED_BY_SAFETY", e.code
        assert mt5.send_count == 0
        print(f"[OK] dry_run blocks: {e}")
        return
    raise AssertionError("DRY_RUN must block order_send")


def test_demo_only_open_close_ok():
    aid = uuid4()
    os.environ["V2_EXECUTION_MODE"] = "DEMO_ONLY"
    os.environ["V2_ORDER_EXECUTION_ENABLED"] = "true"
    os.environ["V2_DEMO_WHITELIST_ACCOUNTS"] = f"{aid}"
    get_v2_settings.cache_clear()

    mt5 = _build_fake_mt5()
    _install_fake_mt5(mt5)
    ex = _mk_executor()

    # OPEN
    r = ex.execute(_mk_task(OrderAction.OPEN, account_id=aid), _session())
    assert r.retcode == mt5.TRADE_RETCODE_DONE
    assert mt5.last_request["type"] == mt5.ORDER_TYPE_BUY
    assert mt5.last_request["volume"] == 0.10
    print(f"[OK] OPEN done retcode={r.retcode} latency={r.order_latency_ms:.2f}ms")

    # Inject a position so CLOSE can find it
    mt5._positions[555] = _Pos(ticket=555, symbol="EURUSD",
                               volume=0.10, side=mt5.POSITION_TYPE_BUY)

    # CLOSE by client_ticket
    r2 = ex.execute(
        _mk_task(OrderAction.CLOSE, account_id=aid, client_ticket=555),
        _session(),
    )
    assert r2.retcode == mt5.TRADE_RETCODE_DONE
    assert mt5.last_request["position"] == 555
    assert mt5.last_request["type"] == mt5.ORDER_TYPE_SELL  # opposite of BUY
    print(f"[OK] CLOSE by ticket=555 retcode={r2.retcode}")


def test_close_requires_client_ticket():
    aid = uuid4()
    os.environ["V2_EXECUTION_MODE"] = "DEMO_ONLY"
    os.environ["V2_ORDER_EXECUTION_ENABLED"] = "true"
    os.environ["V2_DEMO_WHITELIST_ACCOUNTS"] = f"{aid}"
    get_v2_settings.cache_clear()

    mt5 = _build_fake_mt5()
    _install_fake_mt5(mt5)
    ex = _mk_executor()
    try:
        ex.execute(
            _mk_task(OrderAction.CLOSE, account_id=aid, client_ticket=None),
            _session(),
        )
    except ExecutionError as e:
        assert "CLOSE_REQUIRES_CLIENT_TICKET" in str(e)
        assert mt5.send_count == 0
        print(f"[OK] CLOSE without ticket rejected: {e}")
        return
    raise AssertionError("CLOSE without client_ticket must fail")


def test_close_symbol_mismatch_blocked():
    aid = uuid4()
    os.environ["V2_DEMO_WHITELIST_ACCOUNTS"] = f"{aid}"
    get_v2_settings.cache_clear()

    mt5 = _build_fake_mt5()
    _install_fake_mt5(mt5)
    ex = _mk_executor()
    mt5._positions[777] = _Pos(ticket=777, symbol="GBPUSD",
                               volume=0.10, side=mt5.POSITION_TYPE_BUY)
    try:
        ex.execute(
            _mk_task(OrderAction.CLOSE, account_id=aid,
                     symbol="EURUSD", client_ticket=777),
            _session(),
        )
    except ExecutionError as e:
        assert "POSITION_SYMBOL_MISMATCH" in str(e)
        assert mt5.send_count == 0
        print(f"[OK] symbol-mismatch CLOSE blocked: {e}")
        return
    raise AssertionError("symbol-mismatched CLOSE must fail")


def test_circuit_breaker_trips_after_threshold():
    aid = uuid4()
    os.environ["V2_DEMO_WHITELIST_ACCOUNTS"] = f"{aid}"
    get_v2_settings.cache_clear()

    mt5 = _build_fake_mt5(force_retcode=10004)  # not DONE
    _install_fake_mt5(mt5)
    ex = _mk_executor()
    failures = 0
    for i in range(5):
        try:
            ex.execute(_mk_task(OrderAction.OPEN, account_id=aid), _session())
        except ExecutionError:
            failures += 1
    assert failures == 5
    assert ex.cb.is_open(), "circuit breaker must be tripped"
    # next call must short-circuit
    try:
        ex.execute(_mk_task(OrderAction.OPEN, account_id=aid), _session())
    except ExecutionError as e:
        assert e.code == "CIRCUIT_OPEN", e.code
        print(f"[OK] CB tripped after 5 failures, next call: {e.code}")
        return
    raise AssertionError("CB-open call must raise CIRCUIT_OPEN")


def test_rate_limiter_blocks_excess():
    aid = uuid4()
    os.environ["V2_DEMO_WHITELIST_ACCOUNTS"] = f"{aid}"
    os.environ["V2_POOL_RATE_LIMIT_BURST"] = "2"
    os.environ["V2_POOL_RATE_LIMIT_PER_S"] = "0"
    get_v2_settings.cache_clear()

    mt5 = _build_fake_mt5()
    _install_fake_mt5(mt5)
    ex = _mk_executor()
    ok = 0
    blocked = 0
    for _ in range(5):
        try:
            ex.execute(_mk_task(OrderAction.OPEN, account_id=aid), _session())
            ok += 1
        except ExecutionError as e:
            if e.code == "RATE_LIMITED":
                blocked += 1
    assert ok == 2 and blocked == 3, (ok, blocked)
    print(f"[OK] rate limit: ok={ok} rate_limited={blocked}")


def main() -> int:
    test_dry_run_blocks_real_order_send()
    test_demo_only_open_close_ok()
    test_close_requires_client_ticket()
    test_close_symbol_mismatch_blocked()
    test_circuit_breaker_trips_after_threshold()
    test_rate_limiter_blocks_excess()
    print("\nAll OrderExecutor smoke tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
