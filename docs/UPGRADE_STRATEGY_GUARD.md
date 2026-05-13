# Strategy Upgrade Guard

Institutional workflow for changing account strategies without risk.

## The Problem
Switching an account from `LOW` to `MEDIUM` while it has open positions from `LOW` can lead to orphaned orders or incorrect lot sizing during recovery.

## The Solution: Two-Phase Transition
1. **Phase 1: RECOVERY_ONLY**
   - New entries from both OLD and NEW strategies are blocked.
   - Only management of existing symbols is allowed.
   - Status: `upgrade_pending_strategy_switch`.

2. **Phase 2: FULL_SWITCH**
   - Triggered only when `open_positions == 0`.
   - Update `strategy_id` in `account_terminal_map`.
   - Release blocks and allow entries from the NEW strategy.

## Audit Logs
All transitions are recorded with:
- `upgrade_initiated_at`
- `old_strategy_id`
- `new_strategy_id`
- `positions_at_start`
- `switch_completed_at`
