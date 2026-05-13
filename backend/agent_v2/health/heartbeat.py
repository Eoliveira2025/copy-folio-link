"""Heartbeat + watchdog for V2 pools.

Publishes a JSON snapshot per pool to Redis at:
  copytrade_v2:health:pool:{pool_id}        (TTL = HEARTBEAT_TTL_S)

Snapshot fields:
  pool_id, pool_name, master_id, strategy_id,
  status, queue_depth, terminal_alive, circuit_open,
  active_accounts, capacity, login_count, ts.

Watchdog actions:
  * If terminal_alive=False AND circuit_open=True → mark pool FAILED.
  * If queue_depth grows beyond a soft threshold → log warning (no auto
    restart; that lands in a later hardening pass).
"""

from __future__ import annotations

import threading
import time
from typing import Optional

from ..config import get_v2_settings
from ..redis_client import set_json
from ..utils.logger import get_logger
from ..wiring import PoolWorker, PoolWorkerRegistry


class HealthMonitor:
    def __init__(
        self,
        *,
        registry: PoolWorkerRegistry,
        interval_s: Optional[float] = None,
        queue_depth_warn: int = 100,
    ):
        self.registry = registry
        s = get_v2_settings()
        self.interval = interval_s or s.HEALTH_CHECK_INTERVAL_S
        self.ttl = s.HEARTBEAT_TTL_S
        self.queue_depth_warn = queue_depth_warn
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.log = get_logger("health")

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, name="v2-health", daemon=True,
        )
        self._thread.start()
        self.log.info("health monitor started",
                      extra={"action": "health_started",
                             "interval_s": self.interval})

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=timeout)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                for w in self.registry.all():
                    self._tick(w)
            except Exception as e:
                self.log.error("health tick error",
                               extra={"action": "health_tick_error"},
                               exc_info=e)
            self._stop.wait(self.interval)

    def snapshot(self, w: PoolWorker) -> dict:
        return {
            "pool_id": str(w.pool.id),
            "pool_name": w.pool.pool_name,
            "master_id": str(w.pool.master_id),
            "strategy_id": str(w.pool.strategy_id),
            "status": w.pool.status,
            "queue_depth": w.queue.depth(),
            "terminal_alive": w.pool.is_process_alive(),
            "circuit_open": w.executor.cb.is_open(),
            "active_accounts": w.pool.active_accounts_count,
            "capacity": w.pool.capacity,
            "login_count": w.session.login_count(),
            "ts": time.time(),
        }

    def _tick(self, w: PoolWorker) -> None:
        snap = self.snapshot(w)
        try:
            set_json(f"health:pool:{w.pool.id}", snap, ex=self.ttl)
        except Exception as e:
            self.log.warning("heartbeat publish failed",
                             extra={"action": "heartbeat_publish_failed",
                                    "pool_id": snap["pool_id"]}, exc_info=e)

        if snap["queue_depth"] >= self.queue_depth_warn:
            self.log.warning("queue depth high",
                             extra={"action": "queue_depth_high", **snap})

        if snap["circuit_open"] and not snap["terminal_alive"]:
            try:
                w.pool.mark_failed()
            except Exception:
                pass
