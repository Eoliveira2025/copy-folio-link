"""ExecutionQueue — one queue + one worker thread per terminal.

Guarantees:
  * Sequential execution within a single terminal (FIFO).
  * Different queues (different terminals) run in parallel (own threads).
  * Idempotency: tasks with a key already seen are dropped as DUPLICATE.
  * Login failure marks task FAILED and continues with the next task.
  * DRY-RUN: no real `mt5.order_send` here. Real execution lands in inc. 6.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from queue import Queue, Empty
from typing import Callable, Optional
from uuid import UUID

from ..utils.logger import get_logger
from ..exec.order_task import OrderTask, TaskStatus
from .account_session import AccountSession, LoginFailedError


# Type alias: handler receives (task, session_info) and returns retcode-like int.
# In dry-run it's just a no-op stub.
TaskHandler = Callable[[OrderTask, dict], Optional[int]]


def _default_dry_run_handler(task: OrderTask, session_info: dict) -> int:
    # Simulate small order roundtrip
    time.sleep(0.01)
    return 0  # 0 = success placeholder


class _IdempotencyCache:
    """Bounded LRU set of recently seen idempotency keys."""

    def __init__(self, max_entries: int = 5000):
        self._max = max_entries
        self._d: "OrderedDict[str, float]" = OrderedDict()
        self._lock = threading.Lock()

    def seen_or_add(self, key: str) -> bool:
        now = time.time()
        with self._lock:
            if key in self._d:
                self._d.move_to_end(key)
                return True
            self._d[key] = now
            if len(self._d) > self._max:
                self._d.popitem(last=False)
            return False


class ExecutionQueue:
    """Per-terminal serialized executor."""

    def __init__(
        self,
        *,
        pool_id: UUID,
        terminal_id: UUID,
        pool_name: str,
        session: AccountSession,
        account_login_resolver: Callable[[UUID], int],
        handler: TaskHandler = _default_dry_run_handler,
        idempotency_cache: Optional[_IdempotencyCache] = None,
    ):
        self.pool_id = pool_id
        self.terminal_id = terminal_id
        self.pool_name = pool_name
        self.session = session
        self.account_login_resolver = account_login_resolver
        self.handler = handler
        self._idem = idempotency_cache or _IdempotencyCache()
        self._q: "Queue[Optional[OrderTask]]" = Queue()
        self._worker: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self.log = get_logger("queue").bind(
            pool_id=str(pool_id),
            terminal_id=str(terminal_id),
            pool_name=pool_name,
        )

    # ── lifecycle ─────────────────────────────────────────────────
    def start(self) -> None:
        if self._worker and self._worker.is_alive():
            return
        self._stop.clear()
        self._worker = threading.Thread(
            target=self._run,
            name=f"v2-queue-{self.pool_name}",
            daemon=True,
        )
        self._worker.start()
        self.log.info("queue started", extra={"action": "queue_started"})

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        self._q.put(None)  # wake worker
        if self._worker:
            self._worker.join(timeout=timeout)
        self.log.info("queue stopped", extra={"action": "queue_stopped"})

    # ── enqueue ───────────────────────────────────────────────────
    def submit(self, task: OrderTask) -> TaskStatus:
        """Enqueue a task. Returns DUPLICATE if idempotency key was seen."""
        if self._idem.seen_or_add(task.idempotency_key):
            task.status = TaskStatus.DUPLICATE
            self.log.info(
                "task dropped (duplicate)",
                extra={**task.log_fields(), "action": "task_duplicate"},
            )
            return TaskStatus.DUPLICATE
        self._q.put(task)
        self.log.info(
            "task enqueued",
            extra={**task.log_fields(), "action": "task_enqueued",
                   "queue_depth": self._q.qsize()},
        )
        return TaskStatus.QUEUED

    def depth(self) -> int:
        return self._q.qsize()

    # ── worker ────────────────────────────────────────────────────
    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                task = self._q.get(timeout=0.5)
            except Empty:
                continue
            if task is None:
                break
            self._process(task)

    def _process(self, task: OrderTask) -> None:
        task.status = TaskStatus.RUNNING
        log = self.log.bind(**task.log_fields())
        t0 = time.monotonic()
        try:
            login = self.account_login_resolver(task.account_id)
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.failure_reason = f"login_resolver: {e}"
            log.error(
                "task failed (login_resolver)",
                extra={"action": "task_failed"},
                exc_info=e,
            )
            return

        try:
            with self.session.acquire(
                account_id=task.account_id, login=login
            ) as session_info:
                retcode = self.handler(task, session_info)
                latency_ms = (time.monotonic() - t0) * 1000.0
                task.status = TaskStatus.DONE
                log.info(
                    "task done",
                    extra={
                        "action": "task_done",
                        "retcode": retcode,
                        "latency_ms": round(latency_ms, 2),
                        "login_latency_ms": round(
                            session_info.get("login_latency_ms", 0.0), 2
                        ),
                        "switched": session_info.get("switched", False),
                    },
                )
        except LoginFailedError as e:
            task.status = TaskStatus.FAILED
            task.failure_reason = f"login_failed: {e}"
            log.error(
                "task failed (login)",
                extra={"action": "task_failed_login"},
                exc_info=e,
            )
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.failure_reason = f"handler: {e}"
            log.error(
                "task failed (handler)",
                extra={"action": "task_failed_handler"},
                exc_info=e,
            )
