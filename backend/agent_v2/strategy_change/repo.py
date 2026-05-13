"""V2 strategy change requests — persistence layer.

Table: v2_strategy_change_requests (created in migration 016).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from sqlalchemy import text

from ..db import session_scope
from .state_machine import ChangeMode, ChangeState


@dataclass
class ChangeRequestRow:
    id: UUID
    account_id: UUID
    old_strategy_id: UUID
    new_strategy_id: UUID
    old_pool_id: Optional[UUID]
    new_pool_id: Optional[UUID]
    state: ChangeState
    mode: ChangeMode
    floating_pnl: Optional[float]
    requested_by: Optional[UUID]
    approved_by: Optional[UUID]


def create_request(
    *,
    account_id: UUID,
    old_strategy_id: UUID,
    new_strategy_id: UUID,
    mode: ChangeMode,
    requested_by: Optional[UUID] = None,
    old_pool_id: Optional[UUID] = None,
) -> ChangeRequestRow:
    with session_scope() as s:
        row = s.execute(
            text(
                "INSERT INTO v2_strategy_change_requests "
                "(account_id, old_strategy_id, new_strategy_id, old_pool_id, "
                " state, mode, requested_by) "
                "VALUES (:a,:o,:n,:op,:st,:m,:rb) "
                "RETURNING id, account_id, old_strategy_id, new_strategy_id, "
                "old_pool_id, new_pool_id, state, mode, floating_pnl, "
                "requested_by, approved_by"
            ),
            {
                "a": str(account_id),
                "o": str(old_strategy_id),
                "n": str(new_strategy_id),
                "op": str(old_pool_id) if old_pool_id else None,
                "st": ChangeState.PENDING_STRATEGY_CHANGE.value,
                "m": mode.value,
                "rb": str(requested_by) if requested_by else None,
            },
        ).fetchone()
    return _to_dc(row)


def update_state(req_id: UUID, state: ChangeState,
                 *, new_pool_id: Optional[UUID] = None,
                 approved_by: Optional[UUID] = None) -> None:
    sets = ["state=:st", "updated_at=now()"]
    params = {"id": str(req_id), "st": state.value}
    if new_pool_id is not None:
        sets.append("new_pool_id=:np")
        params["np"] = str(new_pool_id)
    if approved_by is not None:
        sets.append("approved_by=:ab")
        params["ab"] = str(approved_by)
    with session_scope() as s:
        s.execute(
            text(f"UPDATE v2_strategy_change_requests SET {', '.join(sets)} "
                 f"WHERE id=:id"),
            params,
        )


def get_open_request_for_account(account_id: UUID) -> Optional[ChangeRequestRow]:
    with session_scope() as s:
        row = s.execute(
            text(
                "SELECT id, account_id, old_strategy_id, new_strategy_id, "
                "old_pool_id, new_pool_id, state, mode, floating_pnl, "
                "requested_by, approved_by "
                "FROM v2_strategy_change_requests "
                "WHERE account_id=:a AND state NOT IN ('SWITCHED','FAILED') "
                "ORDER BY created_at DESC LIMIT 1"
            ),
            {"a": str(account_id)},
        ).fetchone()
    return _to_dc(row) if row else None


def _to_dc(row) -> ChangeRequestRow:
    return ChangeRequestRow(
        id=row.id,
        account_id=row.account_id,
        old_strategy_id=row.old_strategy_id,
        new_strategy_id=row.new_strategy_id,
        old_pool_id=row.old_pool_id,
        new_pool_id=row.new_pool_id,
        state=ChangeState(row.state),
        mode=ChangeMode(row.mode),
        floating_pnl=row.floating_pnl,
        requested_by=row.requested_by,
        approved_by=row.approved_by,
    )
