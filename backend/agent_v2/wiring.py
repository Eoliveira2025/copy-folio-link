"""Wiring helper: builds the per-pool execution chain.

ExecutionQueue → AccountSession → OrderExecutor → CloseReconciler

One PoolWorker per (pool_id, terminal_id). Defaults remain safe:
  * V2_EXECUTION_MODE=DRY_RUN
  * V2_ORDER_EXECUTION_ENABLED=false
  * V2_SESSION_DRY_RUN=true
  * V2_CLOSE_RECONCILER_ENABLED=false

In DRY_RUN the queue's safety guard short-circuits before reaching
OrderExecutor, so `mt5.order_send` is never called.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Callable, Optional
from uuid import UUID

from .config import get_v2_settings
from .exec.close_reconciler import CloseReconciler
from .exec.order_executor import OrderExecutor
from .exec.order_task import OrderAction, OrderTask
from .pool.account_session import AccountSession
from .pool.execution_queue import ExecutionQueue
from .pool.terminal_pool import TerminalPool
from .pool.repo import AccountDetails
from .utils.logger import get_logger


@dataclass
class PoolWorker:
    pool: TerminalPool
    session: AccountSession
    executor: OrderExecutor
    queue: ExecutionQueue
    reconciler: CloseReconciler

    def start(self) -> None:
        self.queue.start()

    def stop(self) -> None:
        self.queue.stop()

    def submit(self, task: OrderTask):
        return self.queue.submit(task)


def build_pool_worker(
    *,
    pool: TerminalPool,
    account_login_resolver: Callable[[UUID], int],
    account_type_resolver: Optional[Callable[[UUID], str]] = None,
) -> PoolWorker:
    """Wire the full chain for a single pool/terminal."""
    log = get_logger("wiring").bind(
        pool_id=str(pool.id), pool_name=pool.pool_name,
        master_id=str(pool.master_id), strategy_id=str(pool.strategy_id),
    )

    session = AccountSession(
        pool_id=pool.id,
        terminal_id=pool.id,  # 1 terminal per pool in current scheme
        terminal_path=pool.terminal_path,
    )

    # When the breaker trips, mark the pool FAILED in DB so allocator
    # stops sending new accounts to it.
    def _on_trip():
        try:
            pool.mark_failed()
        except Exception as e:
            log.error("mark_failed during CB trip failed",
                      extra={"action": "cb_mark_failed_error"}, exc_info=e)

    executor = OrderExecutor(
        pool_id=pool.id, terminal_id=pool.id, pool_name=pool.pool_name,
        master_id=pool.master_id, strategy_id=pool.strategy_id,
        on_circuit_trip=_on_trip,
    )
    reconciler = CloseReconciler(executor=executor)

    queue = ExecutionQueue(
        pool_id=pool.id, terminal_id=pool.id, pool_name=pool.pool_name,
        session=session,
        account_login_resolver=account_login_resolver,
        account_type_resolver=account_type_resolver,
        handler=executor,  # OrderExecutor is callable: (task, session_info)->retcode
    )
    log.info("pool worker wired", extra={"action": "pool_worker_wired"})
    return PoolWorker(pool=pool, session=session, executor=executor,
                      queue=queue, reconciler=reconciler)


class PoolWorkerRegistry:
    """Thread-safe registry of PoolWorker instances keyed by pool_id."""

    def __init__(self):
        self._workers: dict[UUID, PoolWorker] = {}
        self._lock = threading.RLock()

    def get_or_create(
        self,
        pool: TerminalPool,
        *,
        account_login_resolver: Callable[[UUID], int],
        account_type_resolver: Optional[Callable[[UUID], str]] = None,
    ) -> PoolWorker:
        with self._lock:
            w = self._workers.get(pool.id)
            if w:
                return w
            w = build_pool_worker(
                pool=pool,
                account_login_resolver=account_login_resolver,
                account_type_resolver=account_type_resolver,
            )
            w.start()
            self._workers[pool.id] = w
            return w

    def get(self, pool_id: UUID) -> Optional[PoolWorker]:
        with self._lock:
            return self._workers.get(pool_id)

    def all(self) -> list[PoolWorker]:
        with self._lock:
            return list(self._workers.values())

    def stop_all(self) -> None:
        with self._lock:
            for w in self._workers.values():
                try:
                    w.stop()
                except Exception:
                    pass
            self._workers.clear()
