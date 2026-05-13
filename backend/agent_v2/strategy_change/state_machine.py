"""Strategy-change state machine for V2 client accounts.

States:
  ACTIVE                     — copying current strategy
  PENDING_STRATEGY_CHANGE    — change requested, no transition started
  EXIT_ONLY                  — only CLOSE events accepted; no new OPEN
  READY_TO_SWITCH            — no open positions; safe to remap pool
  SWITCHED                   — moved to new strategy; ACTIVE on new pool
  FAILED                     — could not complete change (operator review)

Modes:
  SAFE_DRAIN                 — default. Wait until floating positions
                               close naturally before switch.
  FORCE_CLOSE_AND_SWITCH     — admin-confirmed. Issue CLOSE for all
                               open positions, then switch.

This module is pure logic; persistence lives in `repo.py` and the
orchestrator wires it up.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass


class ChangeState(str, enum.Enum):
    ACTIVE = "ACTIVE"
    PENDING_STRATEGY_CHANGE = "PENDING_STRATEGY_CHANGE"
    EXIT_ONLY = "EXIT_ONLY"
    READY_TO_SWITCH = "READY_TO_SWITCH"
    SWITCHED = "SWITCHED"
    FAILED = "FAILED"


class ChangeMode(str, enum.Enum):
    SAFE_DRAIN = "SAFE_DRAIN"
    FORCE_CLOSE_AND_SWITCH = "FORCE_CLOSE_AND_SWITCH"


_VALID_TRANSITIONS: dict[ChangeState, set[ChangeState]] = {
    ChangeState.ACTIVE: {ChangeState.PENDING_STRATEGY_CHANGE},
    ChangeState.PENDING_STRATEGY_CHANGE: {
        ChangeState.EXIT_ONLY, ChangeState.FAILED,
    },
    ChangeState.EXIT_ONLY: {
        ChangeState.READY_TO_SWITCH, ChangeState.FAILED,
    },
    ChangeState.READY_TO_SWITCH: {ChangeState.SWITCHED, ChangeState.FAILED},
    ChangeState.SWITCHED: set(),  # terminal
    ChangeState.FAILED: {ChangeState.PENDING_STRATEGY_CHANGE},  # retry
}


class IllegalTransition(RuntimeError):
    pass


@dataclass
class TransitionDecision:
    next_state: ChangeState
    reason: str


def transition(current: ChangeState, target: ChangeState) -> TransitionDecision:
    if target not in _VALID_TRANSITIONS.get(current, set()):
        raise IllegalTransition(
            f"cannot move {current.value} -> {target.value}"
        )
    return TransitionDecision(next_state=target,
                              reason=f"{current.value}->{target.value}")


def can_switch(current: ChangeState, has_open_positions: bool,
               mode: ChangeMode) -> bool:
    """Return True if we may move to READY_TO_SWITCH right now."""
    if current != ChangeState.EXIT_ONLY:
        return False
    if not has_open_positions:
        return True
    return mode == ChangeMode.FORCE_CLOSE_AND_SWITCH
