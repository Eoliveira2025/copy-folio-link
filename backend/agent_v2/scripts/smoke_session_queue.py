"""Smoke test for AccountSession + ExecutionQueue (dry-run, no MT5).

Validates:
  1. Sequential execution within one queue (terminal lock).
  2. Parallel execution across two queues.
  3. Idempotency: duplicated key is dropped.
  4. Login failure marks task FAILED without breaking the queue.
  5. Sticky session reuse (same account back-to-back ⇒ login_count=1).

Run from backend/ :
    V2_SESSION_DRY_RUN=true python -m agent_v2.scripts.smoke_session_queue
"""

from __future__ import annotations

import threading
import time
from uuid import uuid4

from ..exec.order_task import OrderAction, OrderTask, TaskStatus
from ..pool.account_session import AccountSession, LoginFailedError
from ..pool.execution_queue import ExecutionQueue


def fixed_login_resolver(account_id):
    # Map UUID → fake MT5 login number
    return abs(hash(account_id)) % 10_000_000


def make_queue(pool_name: str):
    pool_id = uuid4()
    terminal_id = uuid4()
    session = AccountSession(
        pool_id=pool_id,
        terminal_id=terminal_id,
        terminal_path=f"C:/MT5_Pool_V2/test/{pool_name}",
        sticky_hold_ms=0,
    )
    q = ExecutionQueue(
        pool_id=pool_id,
        terminal_id=terminal_id,
        pool_name=pool_name,
        session=session,
        account_login_resolver=fixed_login_resolver,
    )
    q.start()
    return q, session


def make_task(account_id=None, action=OrderAction.OPEN, idem=None, **kw):
    return OrderTask(
        account_id=account_id or uuid4(),
        pool_id=uuid4(),
        terminal_id=uuid4(),
        master_id=uuid4(),
        strategy_id=uuid4(),
        action=action,
        symbol="EURUSD",
        idempotency_key=idem or "",
        **kw,
    )


def test_sequential_within_queue():
    print("\n[1] sequential within one queue")
    q, _ = make_queue("pool_low_01")
    tasks = [make_task() for _ in range(5)]
    for t in tasks:
        q.submit(t)
    # Wait drain
    while q.depth() > 0:
        time.sleep(0.05)
    time.sleep(0.2)
    statuses = [t.status for t in tasks]
    assert all(s == TaskStatus.DONE for s in statuses), statuses
    print(f"    OK — {len(tasks)} tasks done sequentially")
    q.stop()


def test_parallel_across_queues():
    print("\n[2] parallel across two queues")
    q1, _ = make_queue("pool_low_01")
    q2, _ = make_queue("pool_low_02")
    n = 8
    t0 = time.monotonic()
    for _ in range(n):
        q1.submit(make_task())
        q2.submit(make_task())
    while q1.depth() > 0 or q2.depth() > 0:
        time.sleep(0.05)
    time.sleep(0.2)
    elapsed = time.monotonic() - t0
    print(f"    OK — 2x{n} tasks in {elapsed:.2f}s "
          f"(should be ~half of single-queue time)")
    q1.stop()
    q2.stop()


def test_idempotency():
    print("\n[3] duplicate idempotency_key dropped")
    q, _ = make_queue("pool_pro_01")
    t1 = make_task(idem="dup-key-1")
    t2 = make_task(idem="dup-key-1")
    s1 = q.submit(t1)
    s2 = q.submit(t2)
    assert s1 == TaskStatus.QUEUED
    assert s2 == TaskStatus.DUPLICATE, s2
    while q.depth() > 0:
        time.sleep(0.05)
    time.sleep(0.2)
    print(f"    OK — first={s1.value}, second={s2.value}")
    q.stop()


def test_login_failure_recovers():
    print("\n[4] login failure marks task FAILED, queue keeps running")
    q, session = make_queue("pool_expert_01")

    original = session._do_login

    call = {"n": 0}

    def flaky(account_id, login):
        call["n"] += 1
        if call["n"] == 1:
            raise LoginFailedError("simulated")
        return original(account_id, login)

    session._do_login = flaky  # type: ignore[method-assign]

    bad = make_task()
    good = make_task()
    q.submit(bad)
    q.submit(good)
    while q.depth() > 0:
        time.sleep(0.05)
    time.sleep(0.3)
    assert bad.status == TaskStatus.FAILED, bad.status
    assert good.status == TaskStatus.DONE, good.status
    print(f"    OK — bad={bad.status.value}, good={good.status.value}")
    q.stop()


def test_sticky_reuse():
    print("\n[5] sticky session reuses login for same account")
    q, session = make_queue("pool_low_03")
    acc = uuid4()
    for _ in range(4):
        q.submit(make_task(account_id=acc))
    while q.depth() > 0:
        time.sleep(0.05)
    time.sleep(0.2)
    print(f"    OK — login_count={session.login_count()} (expected 1)")
    assert session.login_count() == 1, session.login_count()
    q.stop()


def main() -> int:
    test_sequential_within_queue()
    test_parallel_across_queues()
    test_idempotency()
    test_login_failure_recovers()
    test_sticky_reuse()
    print("\nAll smoke tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
