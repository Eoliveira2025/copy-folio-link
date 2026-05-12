"""Pool repository — raw SQL access to V2 tables.

Keeps V2 self-contained: no import from `backend/app/models/` or V1 modules.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional
from uuid import UUID

from sqlalchemy import text

from ..db import session_scope


VALID_STATUSES = {"ACTIVE", "STANDBY", "DRAINING", "OFFLINE", "FAILED", "STOPPED"}


@dataclass
class PoolRow:
    id: UUID
    pool_name: str
    master_id: UUID
    strategy_id: UUID
    terminal_path: str
    capacity: int
    current_load: int
    status: str
    host: Optional[str]


def _row_to_pool(row) -> PoolRow:
    return PoolRow(
        id=row.id,
        pool_name=row.pool_name,
        master_id=row.master_id,
        strategy_id=row.strategy_id,
        terminal_path=row.terminal_path,
        capacity=row.capacity,
        current_load=row.current_load,
        status=row.status,
        host=row.host,
    )


def list_pools_for_strategy(strategy_id: UUID) -> list[PoolRow]:
    with session_scope() as s:
        rows = s.execute(
            text(
                "SELECT id, pool_name, master_id, strategy_id, terminal_path, "
                "capacity, current_load, status, host "
                "FROM pool_terminal WHERE strategy_id = :sid "
                "ORDER BY pool_name"
            ),
            {"sid": str(strategy_id)},
        ).fetchall()
    return [_row_to_pool(r) for r in rows]


def get_pool_by_name(pool_name: str) -> Optional[PoolRow]:
    with session_scope() as s:
        row = s.execute(
            text(
                "SELECT id, pool_name, master_id, strategy_id, terminal_path, "
                "capacity, current_load, status, host "
                "FROM pool_terminal WHERE pool_name = :n"
            ),
            {"n": pool_name},
        ).fetchone()
    return _row_to_pool(row) if row else None


def insert_pool(
    *,
    pool_name: str,
    master_id: UUID,
    strategy_id: UUID,
    terminal_path: str,
    capacity: int,
    status: str = "STANDBY",
    host: Optional[str] = None,
) -> PoolRow:
    if status not in VALID_STATUSES:
        raise ValueError(f"invalid pool status: {status}")
    with session_scope() as s:
        row = s.execute(
            text(
                "INSERT INTO pool_terminal "
                "(pool_name, master_id, strategy_id, terminal_path, capacity, status, host) "
                "VALUES (:n,:m,:sid,:p,:c,:st,:h) "
                "RETURNING id, pool_name, master_id, strategy_id, terminal_path, "
                "capacity, current_load, status, host"
            ),
            {
                "n": pool_name,
                "m": str(master_id),
                "sid": str(strategy_id),
                "p": terminal_path,
                "c": capacity,
                "st": status,
                "h": host,
            },
        ).fetchone()
    return _row_to_pool(row)


def update_pool_status(pool_id: UUID, status: str) -> None:
    if status not in VALID_STATUSES:
        raise ValueError(f"invalid pool status: {status}")
    with session_scope() as s:
        s.execute(
            text(
                "UPDATE pool_terminal SET status=:st, updated_at=now() "
                "WHERE id=:id"
            ),
            {"st": status, "id": str(pool_id)},
        )


def count_pool_accounts(pool_id: UUID) -> int:
    with session_scope() as s:
        n = s.execute(
            text(
                "SELECT COUNT(*) FROM account_terminal_map WHERE pool_id = :pid"
            ),
            {"pid": str(pool_id)},
        ).scalar_one()
    return int(n)


def next_pool_name(strategy_key: str, existing: Iterable[str]) -> str:
    """Compute next pool name for a strategy, e.g. pool_low_03."""
    used_nums: set[int] = set()
    prefix = f"pool_{strategy_key}_"
    for name in existing:
        if name.startswith(prefix):
            tail = name[len(prefix):]
            if tail.isdigit():
                used_nums.add(int(tail))
    n = 1
    while n in used_nums:
        n += 1
    return f"{prefix}{n:02d}"


# ──────────────────────────────────────────────────────────────────
# account_terminal_map
# ──────────────────────────────────────────────────────────────────
@dataclass
class AccountMappingRow:
    account_id: UUID
    pool_id: UUID
    terminal_id: UUID
    master_id: UUID
    strategy_id: UUID


def get_account_mapping(account_id: UUID) -> Optional[AccountMappingRow]:
    with session_scope() as s:
        row = s.execute(
            text(
                "SELECT account_id, pool_id, terminal_id, master_id, strategy_id "
                "FROM account_terminal_map WHERE account_id = :aid"
            ),
            {"aid": str(account_id)},
        ).fetchone()
    if not row:
        return None
    return AccountMappingRow(
        account_id=row.account_id,
        pool_id=row.pool_id,
        terminal_id=row.terminal_id,
        master_id=row.master_id,
        strategy_id=row.strategy_id,
    )


def insert_account_mapping(
    *,
    account_id: UUID,
    pool_id: UUID,
    terminal_id: UUID,
    master_id: UUID,
    strategy_id: UUID,
) -> AccountMappingRow:
    with session_scope() as s:
        s.execute(
            text(
                "INSERT INTO account_terminal_map "
                "(account_id, pool_id, terminal_id, master_id, strategy_id) "
                "VALUES (:aid,:pid,:tid,:mid,:sid)"
            ),
            {
                "aid": str(account_id),
                "pid": str(pool_id),
                "tid": str(terminal_id),
                "mid": str(master_id),
                "sid": str(strategy_id),
            },
        )
        # bump pool load atomically
        s.execute(
            text(
                "UPDATE pool_terminal SET current_load = current_load + 1, "
                "updated_at = now() WHERE id = :pid"
            ),
            {"pid": str(pool_id)},
        )
    return AccountMappingRow(
        account_id=account_id, pool_id=pool_id, terminal_id=terminal_id,
        master_id=master_id, strategy_id=strategy_id,
    )


def delete_account_mapping(account_id: UUID) -> None:
    with session_scope() as s:
        row = s.execute(
            text("SELECT pool_id FROM account_terminal_map WHERE account_id = :aid"),
            {"aid": str(account_id)},
        ).fetchone()
        if not row:
            return
        s.execute(
            text("DELETE FROM account_terminal_map WHERE account_id = :aid"),
            {"aid": str(account_id)},
        )
        s.execute(
            text(
                "UPDATE pool_terminal SET current_load = GREATEST(current_load - 1, 0), "
                "updated_at = now() WHERE id = :pid"
            ),
            {"pid": str(row.pool_id)},
        )

