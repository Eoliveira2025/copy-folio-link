"""Smoke test for CloseReconciler V2 with a fake MetaTrader5 module.

Scenarios:
  1. Disabled by default → status DISABLED.
  2. Normal close OK on first attempt.
  3. First close fails, position still open; reconciler retries and closes.
  4. User closed manually → JA_NAO_EXISTE (not failed).
  5. Position never existed → JA_NAO_EXISTE (with NOT_FOUND).
  6. WRONG_SYMBOL — position exists for ticket but symbol differs:
     reconciler MUST refuse to close (FALHOU + WRONG_SYMBOL_BLOCKED log).
  7. Fallback by exact comment+magic+symbol when client_ticket missing.
  8. Fallback ambiguous (2 candidates) → AMBIGUOUS_FALLBACK.

No real MT5, no DB. Sleep is monkey-patched.
"""

from __future__ import annotations

import os
import sys
import types
from uuid import uuid4

# Enable reconciler + DEMO mode + whitelisted account BEFORE settings cache
os.environ["V2_EXECUTION_MODE"] = "DEMO_ONLY"
os.environ["V2_ORDER_EXECUTION_ENABLED"] = "true"
os.environ["V2_CLOSE_RECONCILER_MAX_ATTEMPTS"] = "3"
os.environ["V2_CLOSE_RECONCILER_RETRY_DELAYS_SECONDS"] = "0,0,0"
os.environ["V2_POOL_RATE_LIMIT_PER_S"] = "0"
os.environ["V2_POOL_RATE_LIMIT_BURST"] = "100"
os.environ["V2_POOL_CB_FAILURE_THRESHOLD"] = "999"  # don't trip during tests

from agent_v2.config import get_v2_settings  # noqa: E402


# ─────────────────────────────────────────────────────────────────
# Fake MT5
# ─────────────────────────────────────────────────────────────────
class _Tick:
    bid, ask = 1.10, 1.1002


class _Sym:
    volume_min, volume_max, volume_step = 0.01, 100.0, 0.01


class _TI:
    connected = True


class _AI:
    login = 12345678


class _Pos:
    def __init__(self, ticket, symbol="EURUSD", volume=0.10, side=0,
                 magic=42, comment=""):
        self.ticket = ticket
        self.symbol = symbol
        self.volume = volume
        self.type = side
        self.magic = magic
        self.comment = comment


def _build_fake_mt5(*, positions=None, fail_close_first_n=0):
    m = types.SimpleNamespace()
    m.TRADE_ACTION_DEAL = 1
    m.ORDER_TYPE_BUY, m.ORDER_TYPE_SELL = 0, 1
    m.POSITION_TYPE_BUY, m.POSITION_TYPE_SELL = 0, 1
    m.ORDER_TIME_GTC = 0
    m.ORDER_FILLING_IOC = 1
    m.TRADE_RETCODE_DONE = 10009
    m._positions = {p.ticket: p for p in (positions or [])}
    m._fail_n = fail_close_first_n
    m.send_count = 0

    def initialize(**kw): return True
    def shutdown(): return True
    def last_error(): return (1, "fake")
    def terminal_info(): return _TI()
    def account_info(): return _AI()
    def symbol_select(s, on=True): return True
    def symbol_info(s): return _Sym()
    def symbol_info_tick(s): return _Tick()

    def positions_get(ticket=None, symbol=None):
        if ticket is not None:
            p = m._positions.get(int(ticket))
            return [p] if p else []
        return list(m._positions.values())

    class _Res:
        def __init__(self, retcode, comment="ok", deal=1, order=2,
                     price=1.1, volume=0.1):
            self.retcode = retcode
            self.comment = comment
            self.deal = deal
            self.order = order
            self.price = price
            self.volume = volume

    def order_send(req):
        m.send_count += 1
        # Simulate first N close attempts as failures (broker reject) but
        # leave position untouched. After that, succeed and remove pos.
        if m._fail_n > 0:
            m._fail_n -= 1
            return _Res(retcode=10004, comment="REQUOTE")
        # success → remove the targeted position
        pos_ticket = req.get("position")
        if pos_ticket and int(pos_ticket) in m._positions:
            del m._positions[int(pos_ticket)]
        return _Res(retcode=m.TRADE_RETCODE_DONE)

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


def _install(mt5):
    sys.modules["MetaTrader5"] = mt5


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────
from agent_v2.exec.order_task import OrderAction, OrderTask  # noqa: E402
from agent_v2.exec.order_executor import OrderExecutor  # noqa: E402
from agent_v2.exec.close_reconciler import (  # noqa: E402
    CloseReconciler, ReconcileStatus,
)


def _mk_executor():
    return OrderExecutor(
        pool_id=uuid4(), terminal_id=uuid4(), pool_name="pool_demo_01",
        master_id=uuid4(), strategy_id=uuid4(),
    )


def _mk_close_task(aid, *, client_ticket=None, master_ticket=None,
                   symbol="EURUSD", magic=42):
    return OrderTask(
        account_id=aid, pool_id=uuid4(), terminal_id=uuid4(),
        master_id=uuid4(), strategy_id=uuid4(),
        action=OrderAction.CLOSE, symbol=symbol,
        client_ticket=client_ticket, master_ticket=master_ticket,
        magic=magic,
    )


def _whitelist(aid):
    os.environ["V2_DEMO_WHITELIST_ACCOUNTS"] = f"{aid}"
    get_v2_settings.cache_clear()


# ─────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────
def test_disabled_by_default():
    os.environ["V2_CLOSE_RECONCILER_ENABLED"] = "false"
    aid = uuid4(); _whitelist(aid)
    _install(_build_fake_mt5(positions=[_Pos(100)]))
    rec = CloseReconciler(executor=_mk_executor(), sleep_fn=lambda s: None)
    r = rec.reconcile(_mk_close_task(aid, client_ticket=100))
    assert r.status == ReconcileStatus.DISABLED, r.status
    print(f"[OK] disabled: {r.status}")


def test_normal_close_ok():
    os.environ["V2_CLOSE_RECONCILER_ENABLED"] = "true"
    aid = uuid4(); _whitelist(aid)
    mt5 = _build_fake_mt5(positions=[_Pos(101)])
    _install(mt5)
    rec = CloseReconciler(executor=_mk_executor(), sleep_fn=lambda s: None)
    r = rec.reconcile(_mk_close_task(aid, client_ticket=101))
    assert r.status == ReconcileStatus.FECHADO_OK, r.status
    assert r.attempts == 1, r.attempts
    assert 101 not in mt5._positions
    print(f"[OK] normal close: {r.status} attempts={r.attempts}")


def test_close_fails_then_reconciled():
    os.environ["V2_CLOSE_RECONCILER_ENABLED"] = "true"
    aid = uuid4(); _whitelist(aid)
    mt5 = _build_fake_mt5(positions=[_Pos(102)], fail_close_first_n=1)
    _install(mt5)
    rec = CloseReconciler(executor=_mk_executor(), sleep_fn=lambda s: None)
    r = rec.reconcile(_mk_close_task(aid, client_ticket=102))
    assert r.status == ReconcileStatus.FECHADO_OK, r.status
    assert r.attempts == 2, r.attempts
    assert 102 not in mt5._positions
    print(f"[OK] retry then close: {r.status} attempts={r.attempts}")


def test_manual_close_already_gone():
    os.environ["V2_CLOSE_RECONCILER_ENABLED"] = "true"
    aid = uuid4(); _whitelist(aid)
    _install(_build_fake_mt5(positions=[]))  # user already closed
    rec = CloseReconciler(executor=_mk_executor(), sleep_fn=lambda s: None)
    r = rec.reconcile(_mk_close_task(aid, client_ticket=999))
    assert r.status == ReconcileStatus.JA_NAO_EXISTE, r.status
    print(f"[OK] manual close: {r.status}")


def test_wrong_symbol_blocked():
    os.environ["V2_CLOSE_RECONCILER_ENABLED"] = "true"
    aid = uuid4(); _whitelist(aid)
    mt5 = _build_fake_mt5(positions=[_Pos(103, symbol="GBPUSD")])
    _install(mt5)
    rec = CloseReconciler(executor=_mk_executor(), sleep_fn=lambda s: None)
    r = rec.reconcile(_mk_close_task(aid, client_ticket=103, symbol="EURUSD"))
    assert r.status == ReconcileStatus.FALHOU, r.status
    assert 103 in mt5._positions, "must NOT close wrong-symbol position"
    print(f"[OK] wrong symbol blocked: {r.status}")


def test_fallback_by_comment():
    os.environ["V2_CLOSE_RECONCILER_ENABLED"] = "true"
    aid = uuid4(); _whitelist(aid)
    mt5 = _build_fake_mt5(positions=[
        _Pos(200, symbol="EURUSD", magic=42, comment="CT:9999"),
        _Pos(201, symbol="EURUSD", magic=42, comment="CT:other"),
    ])
    _install(mt5)
    rec = CloseReconciler(executor=_mk_executor(), sleep_fn=lambda s: None)
    r = rec.reconcile(_mk_close_task(aid, master_ticket=9999, symbol="EURUSD"))
    assert r.status == ReconcileStatus.FECHADO_OK, r.status
    assert 200 not in mt5._positions
    assert 201 in mt5._positions, "must not touch other positions"
    print(f"[OK] fallback by comment: {r.status} closed=200")


def test_fallback_ambiguous():
    os.environ["V2_CLOSE_RECONCILER_ENABLED"] = "true"
    aid = uuid4(); _whitelist(aid)
    mt5 = _build_fake_mt5(positions=[
        _Pos(300, symbol="EURUSD", magic=42, comment="CT:7777"),
        _Pos(301, symbol="EURUSD", magic=42, comment="CT:7777"),
    ])
    _install(mt5)
    rec = CloseReconciler(executor=_mk_executor(), sleep_fn=lambda s: None)
    r = rec.reconcile(_mk_close_task(aid, master_ticket=7777, symbol="EURUSD"))
    assert r.status == ReconcileStatus.AMBIGUOUS_FALLBACK, r.status
    assert 300 in mt5._positions and 301 in mt5._positions, \
        "ambiguous fallback must NOT close any position"
    print(f"[OK] ambiguous fallback refused: {r.status}")


def main() -> int:
    test_disabled_by_default()
    test_normal_close_ok()
    test_close_fails_then_reconciled()
    test_manual_close_already_gone()
    test_wrong_symbol_blocked()
    test_fallback_by_comment()
    test_fallback_ambiguous()
    print("\nAll CloseReconciler smoke tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
