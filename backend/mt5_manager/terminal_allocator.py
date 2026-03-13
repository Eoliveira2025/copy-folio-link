"""
Terminal Allocator — distributes MT5 accounts across pooled terminals.

Architecture:
  - Each PooledTerminal process manages up to MAX_ACCOUNTS_PER_TERMINAL accounts
  - When all terminals are full, a new terminal is automatically spawned
  - Accounts are assigned to terminals using least-loaded balancing
  - Strategy-aware grouping: accounts on the same strategy prefer the same terminal

Redis keys:
  mt5alloc:terminal:{terminal_id}:accounts  → Set of account_ids
  mt5alloc:account:{account_id}             → terminal_id assignment
  mt5alloc:strategy:{level}:terminals       → Set of terminal_ids serving this strategy
"""

from __future__ import annotations
import logging
import json
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from enum import Enum
import redis
import threading

from mt5_manager.config import get_manager_settings

settings = get_manager_settings()
logger = logging.getLogger("mt5_manager.allocator")


class AllocationStrategy(str, Enum):
    LEAST_LOADED = "least_loaded"
    STRATEGY_AFFINITY = "strategy_affinity"
    ROUND_ROBIN = "round_robin"


@dataclass
class TerminalSlot:
    """Represents a pooled terminal and its account assignments."""
    terminal_id: str
    accounts: Set[str] = field(default_factory=set)
    strategy_groups: Dict[str, Set[str]] = field(default_factory=dict)  # strategy → set of account_ids
    max_accounts: int = 50
    is_healthy: bool = True

    @property
    def load(self) -> float:
        return len(self.accounts) / self.max_accounts if self.max_accounts > 0 else 1.0

    @property
    def available_slots(self) -> int:
        return max(0, self.max_accounts - len(self.accounts))

    @property
    def is_full(self) -> bool:
        return len(self.accounts) >= self.max_accounts


class TerminalAllocator:
    """
    Manages the mapping of MT5 accounts to pooled terminal processes.

    Supports:
      - Least-loaded allocation (default)
      - Strategy-affinity grouping (accounts on same strategy share terminals)
      - Automatic terminal spawning when capacity is exceeded
      - Rebalancing when terminals fail
    """

    def __init__(self):
        self.slots: Dict[str, TerminalSlot] = {}  # terminal_id → TerminalSlot
        self.account_map: Dict[str, str] = {}  # account_id → terminal_id
        self.redis_client = redis.from_url(settings.REDIS_URL)
        self._lock = threading.Lock()
        self._strategy = AllocationStrategy.STRATEGY_AFFINITY
        self._max_accounts_per_terminal = settings.MAX_ACCOUNTS_PER_TERMINAL

    def register_terminal(self, terminal_id: str) -> TerminalSlot:
        """Register a new terminal in the allocation pool."""
        with self._lock:
            slot = TerminalSlot(
                terminal_id=terminal_id,
                max_accounts=self._max_accounts_per_terminal,
            )
            self.slots[terminal_id] = slot
            self._sync_to_redis(terminal_id)
            logger.info(f"Registered terminal {terminal_id} (capacity: {self._max_accounts_per_terminal})")
            return slot

    def unregister_terminal(self, terminal_id: str) -> List[str]:
        """Remove a terminal and return its orphaned account_ids for reassignment."""
        with self._lock:
            slot = self.slots.pop(terminal_id, None)
            if not slot:
                return []

            orphaned = list(slot.accounts)
            for account_id in orphaned:
                self.account_map.pop(account_id, None)

            self.redis_client.delete(f"mt5alloc:terminal:{terminal_id}:accounts")
            logger.info(f"Unregistered terminal {terminal_id}, {len(orphaned)} accounts orphaned")
            return orphaned

    def allocate(self, account_id: str, strategy_level: str = "medium") -> Optional[str]:
        """
        Assign an account to an optimal terminal.
        Returns the terminal_id, or None if no capacity is available.
        """
        with self._lock:
            # Already allocated?
            if account_id in self.account_map:
                existing = self.account_map[account_id]
                if existing in self.slots and not self.slots[existing].is_full:
                    return existing

            terminal_id = None

            if self._strategy == AllocationStrategy.STRATEGY_AFFINITY:
                terminal_id = self._allocate_by_strategy(strategy_level)

            if terminal_id is None:
                terminal_id = self._allocate_least_loaded()

            if terminal_id is None:
                # All terminals full — signal that a new one is needed
                terminal_id = self._request_new_terminal()

            if terminal_id is None:
                logger.error(f"Cannot allocate account {account_id}: no capacity")
                return None

            # Assign
            slot = self.slots[terminal_id]
            slot.accounts.add(account_id)
            if strategy_level not in slot.strategy_groups:
                slot.strategy_groups[strategy_level] = set()
            slot.strategy_groups[strategy_level].add(account_id)
            self.account_map[account_id] = terminal_id

            self._sync_to_redis(terminal_id)
            self.redis_client.set(f"mt5alloc:account:{account_id}", terminal_id)

            logger.info(
                f"Allocated account {account_id} → terminal {terminal_id} "
                f"(load: {slot.load:.0%}, strategy: {strategy_level})"
            )
            return terminal_id

    def deallocate(self, account_id: str) -> Optional[str]:
        """Remove an account from its terminal. Returns the terminal_id it was on."""
        with self._lock:
            terminal_id = self.account_map.pop(account_id, None)
            if not terminal_id or terminal_id not in self.slots:
                return None

            slot = self.slots[terminal_id]
            slot.accounts.discard(account_id)
            for group in slot.strategy_groups.values():
                group.discard(account_id)

            self._sync_to_redis(terminal_id)
            self.redis_client.delete(f"mt5alloc:account:{account_id}")

            logger.info(f"Deallocated account {account_id} from terminal {terminal_id}")
            return terminal_id

    def get_terminal_for_account(self, account_id: str) -> Optional[str]:
        """Look up which terminal an account is assigned to."""
        return self.account_map.get(account_id)

    def rebalance(self) -> Dict[str, List[str]]:
        """
        Rebalance accounts across terminals for even load distribution.
        Returns a map of terminal_id → [accounts to migrate].
        """
        with self._lock:
            healthy_slots = [s for s in self.slots.values() if s.is_healthy]
            if not healthy_slots:
                return {}

            total_accounts = sum(len(s.accounts) for s in healthy_slots)
            target_per_terminal = total_accounts // len(healthy_slots)

            migrations: Dict[str, List[str]] = {}

            # Find overloaded terminals
            overloaded = [s for s in healthy_slots if len(s.accounts) > target_per_terminal + 5]
            underloaded = [s for s in healthy_slots if len(s.accounts) < target_per_terminal - 5]

            for over_slot in overloaded:
                excess = len(over_slot.accounts) - target_per_terminal
                accounts_to_move = list(over_slot.accounts)[:excess]

                for account_id in accounts_to_move:
                    for under_slot in underloaded:
                        if not under_slot.is_full:
                            if over_slot.terminal_id not in migrations:
                                migrations[over_slot.terminal_id] = []
                            migrations[over_slot.terminal_id].append(account_id)

                            over_slot.accounts.discard(account_id)
                            under_slot.accounts.add(account_id)
                            self.account_map[account_id] = under_slot.terminal_id
                            break

            if migrations:
                logger.info(f"Rebalance plan: {sum(len(v) for v in migrations.values())} account migrations")

            return migrations

    def get_allocation_summary(self) -> dict:
        """Return allocation overview for monitoring."""
        return {
            "total_terminals": len(self.slots),
            "total_accounts": len(self.account_map),
            "capacity": sum(s.max_accounts for s in self.slots.values()),
            "utilization": len(self.account_map) / max(1, sum(s.max_accounts for s in self.slots.values())),
            "terminals": [
                {
                    "terminal_id": s.terminal_id,
                    "accounts": len(s.accounts),
                    "max": s.max_accounts,
                    "load": f"{s.load:.0%}",
                    "healthy": s.is_healthy,
                    "strategies": {k: len(v) for k, v in s.strategy_groups.items()},
                }
                for s in self.slots.values()
            ],
        }

    # ── Private helpers ──────────────────────────────────────────────

    def _allocate_by_strategy(self, strategy_level: str) -> Optional[str]:
        """Find a terminal that already serves this strategy and has capacity."""
        candidates = [
            s for s in self.slots.values()
            if s.is_healthy
            and not s.is_full
            and strategy_level in s.strategy_groups
            and len(s.strategy_groups[strategy_level]) > 0
        ]
        if candidates:
            # Pick the one with most accounts of this strategy (affinity)
            best = max(candidates, key=lambda s: len(s.strategy_groups.get(strategy_level, set())))
            return best.terminal_id
        return None

    def _allocate_least_loaded(self) -> Optional[str]:
        """Find the terminal with the most available slots."""
        candidates = [s for s in self.slots.values() if s.is_healthy and not s.is_full]
        if candidates:
            best = min(candidates, key=lambda s: s.load)
            return best.terminal_id
        return None

    def _request_new_terminal(self) -> Optional[str]:
        """Signal that a new terminal needs to be spawned. Returns the new terminal_id."""
        total = len(self.slots)
        max_terminals = settings.MAX_TERMINALS

        if total >= max_terminals:
            logger.error(f"Cannot spawn new terminal: limit reached ({max_terminals})")
            return None

        new_id = f"terminal-{uuid.uuid4().hex[:8]}"
        self.register_terminal(new_id)

        # Publish spawn request to Redis for the pool manager
        self.redis_client.publish("mt5mgr:spawn_terminal", json.dumps({
            "terminal_id": new_id,
            "reason": "capacity_overflow",
            "current_terminals": total,
        }))

        logger.info(f"Requested new terminal spawn: {new_id}")
        return new_id

    def _sync_to_redis(self, terminal_id: str):
        """Sync terminal assignment state to Redis."""
        slot = self.slots.get(terminal_id)
        if not slot:
            return
        key = f"mt5alloc:terminal:{terminal_id}:accounts"
        pipe = self.redis_client.pipeline()
        pipe.delete(key)
        if slot.accounts:
            pipe.sadd(key, *slot.accounts)
        pipe.set(f"mt5alloc:terminal:{terminal_id}:meta", json.dumps({
            "load": slot.load,
            "accounts": len(slot.accounts),
            "max": slot.max_accounts,
            "healthy": slot.is_healthy,
        }), ex=300)
        pipe.execute()
