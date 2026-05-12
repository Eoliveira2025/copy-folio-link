"""TerminalPool — represents one MT5 terminal folder dedicated to a single
(master_id, strategy_id).

This increment focuses on:
  * in-memory pool object that mirrors a `pool_terminal` row
  * lifecycle hooks: mark_active, mark_draining, mark_failed, mark_stopped
  * cross-strategy guard: refuses any account whose strategy_id mismatches
  * basic process liveness check (best-effort; no real MT5 init yet)
  * pool registry per (master, strategy) with prewarm

NO real terminal spawn, NO login, NO order execution here.
Those land in increment 3.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID

from ..config import get_v2_settings
from ..utils.logger import get_logger
from . import repo
from .auto_provisioner import AutoProvisioner

POOL_STATUSES_ACCEPTING = {"ACTIVE"}
POOL_STATUSES_RESERVED = {"STANDBY"}
POOL_STATUSES_TERMINAL = {"FAILED", "STOPPED"}


class StrategyMismatchError(RuntimeError):
    """Raised when an account is offered to a pool of a different strategy."""


class PoolFullError(RuntimeError):
    """Raised when no ACTIVE pool can accept a new account."""


@dataclass
class TerminalPool:
    """Lightweight in-memory handle around a `pool_terminal` row."""

    id: UUID
    pool_name: str
    master_id: UUID
    strategy_id: UUID
    terminal_path: str
    capacity: int
    status: str
    active_accounts_count: int = 0
    host: Optional[str] = None

    # process handle (placeholder until increment 3)
    _process_pid: Optional[int] = field(default=None, repr=False)
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    # ── construction ──────────────────────────────────────────────
    @classmethod
    def from_row(cls, row: repo.PoolRow) -> "TerminalPool":
        load = repo.count_pool_accounts(row.id)
        return cls(
            id=row.id,
            pool_name=row.pool_name,
            master_id=row.master_id,
            strategy_id=row.strategy_id,
            terminal_path=row.terminal_path,
            capacity=row.capacity,
            status=row.status,
            active_accounts_count=load,
            host=row.host,
        )

    # ── guards ────────────────────────────────────────────────────
    def assert_strategy(self, strategy_id: UUID) -> None:
        if strategy_id != self.strategy_id:
            raise StrategyMismatchError(
                f"pool {self.pool_name} serves strategy {self.strategy_id}, "
                f"got {strategy_id}"
            )

    def can_accept(self, strategy_id: UUID) -> bool:
        return (
            self.status in POOL_STATUSES_ACCEPTING
            and strategy_id == self.strategy_id
            and self.active_accounts_count < self.capacity
        )

    # ── status transitions ────────────────────────────────────────
    def _transition(self, new_status: str) -> None:
        with self._lock:
            old = self.status
            self.status = new_status
            repo.update_pool_status(self.id, new_status)
            _log(self).info(
                "pool status changed",
                extra={"action": "pool_status_change", "from": old, "to": new_status},
            )

    def mark_active(self) -> None:
        self._transition("ACTIVE")

    def mark_standby(self) -> None:
        self._transition("STANDBY")

    def mark_draining(self) -> None:
        self._transition("DRAINING")

    def mark_failed(self) -> None:
        self._transition("FAILED")

    def mark_stopped(self) -> None:
        self._transition("STOPPED")

    # ── liveness (placeholder) ────────────────────────────────────
    def is_process_alive(self) -> bool:
        """Best-effort check; real spawn happens in increment 3."""
        if not self._process_pid:
            return False
        try:
            os.kill(self._process_pid, 0)
            return True
        except OSError:
            return False


def _log(p: "TerminalPool"):
    return get_logger("pool").bind(
        master_id=str(p.master_id),
        strategy_id=str(p.strategy_id),
        pool_id=str(p.id),
        pool_name=p.pool_name,
    )


# ──────────────────────────────────────────────────────────────────
# StrategyPoolRegistry
# ──────────────────────────────────────────────────────────────────
class StrategyPoolRegistry:
    """Holds all pools for a single (master_id, strategy_id) tuple.

    Provides:
      - `ensure_prewarm()` : guarantees 1 ACTIVE + N STANDBY pools exist
      - `pick_active()`    : returns an ACTIVE pool with capacity
      - `promote_standby()`: promotes a STANDBY pool to ACTIVE (and
                             auto-provisions a fresh STANDBY in background)
    """

    def __init__(
        self,
        *,
        master_id: UUID,
        strategy_id: UUID,
        strategy_key: str,
        provisioner: Optional[AutoProvisioner] = None,
    ):
        self.master_id = master_id
        self.strategy_id = strategy_id
        self.strategy_key = strategy_key
        self.provisioner = provisioner or AutoProvisioner()
        self.settings = get_v2_settings()
        self._lock = threading.RLock()
        self._pools: dict[UUID, TerminalPool] = {}
        self.log = get_logger("pool_registry").bind(
            master_id=str(master_id),
            strategy_id=str(strategy_id),
        )

    # ── load / refresh ────────────────────────────────────────────
    def load_from_db(self) -> None:
        with self._lock:
            self._pools.clear()
            for row in repo.list_pools_for_strategy(self.strategy_id):
                if row.master_id != self.master_id:
                    continue
                self._pools[row.id] = TerminalPool.from_row(row)
        self.log.info(
            "registry loaded",
            extra={"action": "registry_loaded", "pool_count": len(self._pools)},
        )

    # ── inventory ─────────────────────────────────────────────────
    def pools(self) -> list[TerminalPool]:
        with self._lock:
            return list(self._pools.values())

    def actives(self) -> list[TerminalPool]:
        return [p for p in self.pools() if p.status == "ACTIVE"]

    def standbys(self) -> list[TerminalPool]:
        return [p for p in self.pools() if p.status == "STANDBY"]

    # ── provisioning ──────────────────────────────────────────────
    def _provision(self, status: str) -> TerminalPool:
        row = self.provisioner.provision(
            master_id=self.master_id,
            strategy_id=self.strategy_id,
            strategy_key=self.strategy_key,
            status=status,
        )
        pool = TerminalPool.from_row(row)
        with self._lock:
            self._pools[pool.id] = pool
        return pool

    def ensure_prewarm(self) -> None:
        """Guarantee 1 ACTIVE + POOL_PREWARM_STANDBY STANDBY pools exist."""
        if not self.settings.POOL_AUTOPROVISION_ENABLED:
            self.log.info(
                "autoprovision disabled; skipping prewarm",
                extra={"action": "prewarm_skipped"},
            )
            return

        if not self.actives():
            self._provision(status="ACTIVE")

        missing = self.settings.POOL_PREWARM_STANDBY - len(self.standbys())
        for _ in range(max(0, missing)):
            self._provision(status="STANDBY")

        self.log.info(
            "prewarm complete",
            extra={
                "action": "prewarm_complete",
                "actives": len(self.actives()),
                "standbys": len(self.standbys()),
            },
        )

    # ── selection ─────────────────────────────────────────────────
    def pick_active(self) -> TerminalPool:
        """Return ACTIVE pool with lowest load. Promote STANDBY if needed."""
        with self._lock:
            actives_with_room = sorted(
                (p for p in self.actives()
                 if p.active_accounts_count < p.capacity),
                key=lambda p: p.active_accounts_count,
            )
            if actives_with_room:
                return actives_with_room[0]

            # All actives full → promote a standby
            standbys = self.standbys()
            if standbys:
                pool = standbys[0]
                pool.mark_active()
                # Fire-and-forget refill of standby pool
                if self.settings.POOL_AUTOPROVISION_ENABLED:
                    try:
                        self._provision(status="STANDBY")
                    except Exception as e:
                        self.log.error(
                            "standby refill failed",
                            extra={"action": "standby_refill_failed"},
                            exc_info=e,
                        )
                return pool

            # No standby — provision new ACTIVE if allowed
            if self.settings.POOL_AUTOPROVISION_ENABLED:
                pool = self._provision(status="ACTIVE")
                return pool

        raise PoolFullError(
            f"no capacity for strategy {self.strategy_id} and autoprovision disabled"
        )
