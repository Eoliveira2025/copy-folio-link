"""TerminalAllocator — assigns accounts to pools and persists the mapping.

Rules enforced:
  * Strict segmentation: an account is ONLY ever placed in a pool that
    serves the same (master_id, strategy_id). Cross-strategy assignment
    raises StrategyMismatchError.
  * Sticky: if account already mapped, the existing pool/terminal is
    returned (and we re-validate strategy/master).
  * Capacity: when the active pool fills, StrategyPoolRegistry is asked
    to promote a STANDBY (or auto-provision a fresh ACTIVE).
  * Persistence: mapping is written to `account_terminal_map` and the
    pool's `current_load` is incremented atomically by the repo.

NO order execution. NO mt5.order_send. NO terminal spawn here.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from ..utils.logger import get_logger
from . import repo
from .auto_provisioner import AutoProvisioner
from .terminal_pool import (
    StrategyMismatchError,
    StrategyPoolRegistry,
    TerminalPool,
)


@dataclass
class Assignment:
    account_id: UUID
    pool_id: UUID
    terminal_id: UUID
    master_id: UUID
    strategy_id: UUID
    pool_name: str
    reused: bool  # True when we found an existing mapping


class TerminalAllocator:
    """Assigns accounts to pools and persists the binding.

    A single allocator can serve many (master, strategy) pairs. Registries
    are created lazily and cached.
    """

    def __init__(
        self,
        *,
        strategy_key_resolver,
        provisioner: Optional[AutoProvisioner] = None,
    ):
        """
        Args:
            strategy_key_resolver: callable(strategy_id: UUID) -> str
                Returns the folder-safe key (e.g. "low", "pro", "expert").
            provisioner: shared AutoProvisioner (optional).
        """
        self._strategy_key_resolver = strategy_key_resolver
        self._provisioner = provisioner or AutoProvisioner()
        self._registries: dict[tuple[UUID, UUID], StrategyPoolRegistry] = {}
        self._lock = threading.RLock()
        self.log = get_logger("allocator")

    # ── registries ────────────────────────────────────────────────
    def registry(self, master_id: UUID, strategy_id: UUID) -> StrategyPoolRegistry:
        key = (master_id, strategy_id)
        with self._lock:
            reg = self._registries.get(key)
            if reg:
                return reg
            reg = StrategyPoolRegistry(
                master_id=master_id,
                strategy_id=strategy_id,
                strategy_key=self._strategy_key_resolver(strategy_id),
                provisioner=self._provisioner,
            )
            reg.load_from_db()
            reg.ensure_prewarm()
            self._registries[key] = reg
            return reg

    # ── public API ────────────────────────────────────────────────
    def assign(
        self,
        *,
        account_id: UUID,
        master_id: UUID,
        strategy_id: UUID,
    ) -> Assignment:
        """Return existing mapping or create a new one for (account)."""
        log = self.log.bind(
            account_id=str(account_id),
            master_id=str(master_id),
            strategy_id=str(strategy_id),
        )

        # 1) Sticky mapping
        existing = repo.get_account_mapping(account_id)
        if existing:
            if existing.strategy_id != strategy_id:
                raise StrategyMismatchError(
                    f"account {account_id} already mapped to strategy "
                    f"{existing.strategy_id}, refusing to remap to {strategy_id}"
                )
            if existing.master_id != master_id:
                raise StrategyMismatchError(
                    f"account {account_id} already mapped to master "
                    f"{existing.master_id}, refusing to remap to {master_id}"
                )
            log.info(
                "mapping reused",
                extra={
                    "action": "mapping_reused",
                    "pool_id": str(existing.pool_id),
                    "terminal_id": str(existing.terminal_id),
                },
            )
            return Assignment(
                account_id=account_id,
                pool_id=existing.pool_id,
                terminal_id=existing.terminal_id,
                master_id=master_id,
                strategy_id=strategy_id,
                pool_name="",  # unknown without lookup; not needed by callers
                reused=True,
            )

        # 2) Pick / promote / provision
        reg = self.registry(master_id, strategy_id)
        with self._lock:
            pool: TerminalPool = reg.pick_active()
            # Defense-in-depth strategy guard
            pool.assert_strategy(strategy_id)
            if pool.master_id != master_id:
                raise StrategyMismatchError(
                    f"pool {pool.pool_name} belongs to master {pool.master_id}, "
                    f"not {master_id}"
                )

            # 3) Persist mapping (and bump pool load in DB)
            row = repo.insert_account_mapping(
                account_id=account_id,
                pool_id=pool.id,
                terminal_id=pool.id,  # 1 terminal per pool in this increment
                master_id=master_id,
                strategy_id=strategy_id,
            )
            pool.active_accounts_count += 1

        log.info(
            "account assigned",
            extra={
                "action": "account_assigned",
                "pool_id": str(pool.id),
                "pool_name": pool.pool_name,
                "terminal_id": str(pool.id),
                "pool_load": pool.active_accounts_count,
                "pool_capacity": pool.capacity,
            },
        )
        return Assignment(
            account_id=row.account_id,
            pool_id=row.pool_id,
            terminal_id=row.terminal_id,
            master_id=row.master_id,
            strategy_id=row.strategy_id,
            pool_name=pool.pool_name,
            reused=False,
        )

    def release(self, account_id: UUID) -> None:
        """Remove mapping (used on account deletion or strategy migration)."""
        existing = repo.get_account_mapping(account_id)
        repo.delete_account_mapping(account_id)
        if existing:
            # Best-effort: refresh in-memory pool load
            for reg in self._registries.values():
                for pool in reg.pools():
                    if pool.id == existing.pool_id:
                        pool.active_accounts_count = max(
                            0, pool.active_accounts_count - 1
                        )
                        break
            self.log.info(
                "mapping released",
                extra={
                    "action": "mapping_released",
                    "account_id": str(account_id),
                    "pool_id": str(existing.pool_id),
                },
            )
