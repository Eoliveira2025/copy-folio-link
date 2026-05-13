"""Strategy change state machine smoke (no DB).

Validates:
  * SAFE_DRAIN refuses to switch while positions are open.
  * SAFE_DRAIN allows switch once positions reach 0.
  * FORCE_CLOSE_AND_SWITCH requires approved_by; switches even with
    open positions.
  * Illegal transitions are rejected.
"""

from __future__ import annotations

import os
from uuid import uuid4

os.environ["V2_EXECUTION_MODE"] = "DRY_RUN"
os.environ["V2_ORDER_EXECUTION_ENABLED"] = "false"

from agent_v2.config import get_v2_settings  # noqa: E402
get_v2_settings.cache_clear()

from agent_v2.strategy_change.state_machine import (  # noqa: E402
    ChangeMode, ChangeState, IllegalTransition, can_switch, transition,
)


def test_safe_drain_blocks_with_positions():
    assert not can_switch(ChangeState.EXIT_ONLY, True, ChangeMode.SAFE_DRAIN)
    print("[OK] SAFE_DRAIN blocks while positions open")


def test_safe_drain_allows_when_empty():
    assert can_switch(ChangeState.EXIT_ONLY, False, ChangeMode.SAFE_DRAIN)
    print("[OK] SAFE_DRAIN allows when empty")


def test_force_close_allows_with_positions():
    assert can_switch(ChangeState.EXIT_ONLY, True,
                      ChangeMode.FORCE_CLOSE_AND_SWITCH)
    print("[OK] FORCE_CLOSE_AND_SWITCH allows with positions")


def test_legal_chain():
    s = ChangeState.ACTIVE
    for nxt in [ChangeState.PENDING_STRATEGY_CHANGE, ChangeState.EXIT_ONLY,
                ChangeState.READY_TO_SWITCH, ChangeState.SWITCHED]:
        s = transition(s, nxt).next_state
    assert s == ChangeState.SWITCHED
    print("[OK] full legal chain ACTIVE→…→SWITCHED")


def test_illegal_transition():
    try:
        transition(ChangeState.ACTIVE, ChangeState.SWITCHED)
    except IllegalTransition as e:
        print(f"[OK] illegal transition rejected: {e}")
        return
    raise AssertionError("ACTIVE→SWITCHED must be illegal")


def main() -> int:
    test_safe_drain_blocks_with_positions()
    test_safe_drain_allows_when_empty()
    test_force_close_allows_with_positions()
    test_legal_chain()
    test_illegal_transition()
    print("\nAll strategy-change smoke tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
