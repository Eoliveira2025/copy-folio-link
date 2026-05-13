"""Strategy change orchestrator.

High-level flow per request:

  ACTIVE
    └─ request_change(account, new_strategy, mode)
       INSERT row state=PENDING_STRATEGY_CHANGE
       └─ start_drain(req)             ──► EXIT_ONLY
          └─ poll: if positions == 0 OR mode=FORCE_CLOSE_AND_SWITCH and
                   we issued CLOSE for all → READY_TO_SWITCH
             └─ commit_switch(req)     ──► SWITCHED (remap pool)

Defensive rules:
  * Never migrate an account with open positions in SAFE_DRAIN.
  * FORCE_CLOSE_AND_SWITCH requires `approved_by` set (admin).
  * One open request per account at a time.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional
from uuid import UUID

from ..pool.allocator import TerminalAllocator
from ..utils.logger import get_logger
from . import repo
from .state_machine import (
    ChangeMode, ChangeState, IllegalTransition, can_switch, transition,
)


PositionCounter = Callable[[UUID], int]   # account_id -> open positions count


class StrategyChangeError(RuntimeError):
    pass


@dataclass
class ChangeContext:
    account_id: UUID
    old_strategy_id: UUID
    new_strategy_id: UUID
    new_master_id: UUID
    mode: ChangeMode


class StrategyChangeOrchestrator:
    def __init__(
        self,
        *,
        allocator: TerminalAllocator,
        position_counter: PositionCounter,
    ):
        self.allocator = allocator
        self.count_open = position_counter
        self.log = get_logger("strategy_change")

    # ── request ───────────────────────────────────────────────────
    def request_change(self, ctx: ChangeContext,
                       requested_by: Optional[UUID] = None) -> repo.ChangeRequestRow:
        existing = repo.get_open_request_for_account(ctx.account_id)
        if existing:
            raise StrategyChangeError(
                f"account {ctx.account_id} already has open request {existing.id}"
            )
        row = repo.create_request(
            account_id=ctx.account_id,
            old_strategy_id=ctx.old_strategy_id,
            new_strategy_id=ctx.new_strategy_id,
            mode=ctx.mode,
            requested_by=requested_by,
        )
        self.log.info(
            "strategy change requested",
            extra={
                "action": "strategy_change_requested",
                "account_id": str(ctx.account_id),
                "old_strategy_id": str(ctx.old_strategy_id),
                "new_strategy_id": str(ctx.new_strategy_id),
                "mode": ctx.mode.value,
                "request_id": str(row.id),
            },
        )
        return row

    # ── drain ─────────────────────────────────────────────────────
    def start_drain(self, req: repo.ChangeRequestRow) -> None:
        decision = transition(req.state, ChangeState.EXIT_ONLY)
        repo.update_state(req.id, decision.next_state)
        self.log.info("drain started",
                      extra={"action": "drain_started",
                             "request_id": str(req.id),
                             "account_id": str(req.account_id)})

    # ── advance ───────────────────────────────────────────────────
    def maybe_advance(self, req: repo.ChangeRequestRow,
                      *, approved_by: Optional[UUID] = None) -> ChangeState:
        """Move to READY_TO_SWITCH if conditions allow. Returns new state."""
        open_count = self.count_open(req.account_id)
        if not can_switch(req.state, open_count > 0, req.mode):
            return req.state

        if (req.mode == ChangeMode.FORCE_CLOSE_AND_SWITCH
                and approved_by is None and req.approved_by is None):
            raise StrategyChangeError(
                "FORCE_CLOSE_AND_SWITCH requires approved_by"
            )
        try:
            decision = transition(req.state, ChangeState.READY_TO_SWITCH)
        except IllegalTransition as e:
            raise StrategyChangeError(str(e))
        repo.update_state(req.id, decision.next_state, approved_by=approved_by)
        self.log.info(
            "ready to switch",
            extra={"action": "ready_to_switch",
                   "request_id": str(req.id),
                   "account_id": str(req.account_id),
                   "mode": req.mode.value,
                   "open_positions": open_count},
        )
        return decision.next_state

    # ── commit ────────────────────────────────────────────────────
    def commit_switch(self, req: repo.ChangeRequestRow,
                      ctx: ChangeContext) -> repo.ChangeRequestRow:
        if req.state != ChangeState.READY_TO_SWITCH:
            raise StrategyChangeError(
                f"cannot commit from state {req.state.value}"
            )
        # Hard guard: never migrate with open positions unless FORCE
        if self.count_open(req.account_id) > 0 \
                and req.mode != ChangeMode.FORCE_CLOSE_AND_SWITCH:
            raise StrategyChangeError(
                "open positions remain; refuse to switch in SAFE_DRAIN"
            )

        # Drop old mapping, then assign in the new strategy
        self.allocator.release(req.account_id)
        new_assignment = self.allocator.assign(
            account_id=req.account_id,
            master_id=ctx.new_master_id,
            strategy_id=ctx.new_strategy_id,
        )
        decision = transition(req.state, ChangeState.SWITCHED)
        repo.update_state(req.id, decision.next_state,
                          new_pool_id=new_assignment.pool_id)
        self.log.info(
            "strategy switched",
            extra={
                "action": "strategy_switched",
                "request_id": str(req.id),
                "account_id": str(req.account_id),
                "old_strategy_id": str(req.old_strategy_id),
                "new_strategy_id": str(ctx.new_strategy_id),
                "old_pool_id": str(req.old_pool_id) if req.old_pool_id else None,
                "new_pool_id": str(new_assignment.pool_id),
            },
        )
        return repo.get_open_request_for_account(req.account_id) or req

    def fail(self, req: repo.ChangeRequestRow, reason: str) -> None:
        try:
            decision = transition(req.state, ChangeState.FAILED)
            repo.update_state(req.id, decision.next_state)
        except IllegalTransition:
            pass
        self.log.error(
            "strategy change failed",
            extra={"action": "strategy_change_failed",
                   "request_id": str(req.id), "reason": reason},
        )
