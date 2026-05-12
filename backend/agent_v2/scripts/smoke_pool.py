"""V2 pool smoke test — no real MT5 / no real accounts.

Usage (from backend/ directory, with V2 env loaded):

    python -m agent_v2.scripts.smoke_pool \\
        --master-id <uuid> --strategy-id <uuid> --strategy-key low

What it does:
  1. Creates StrategyPoolRegistry for (master, strategy)
  2. Loads existing pools from DB
  3. Calls ensure_prewarm() → expects 1 ACTIVE + N STANDBY pools
  4. Calls pick_active() a few times to validate selection
  5. Demonstrates strategy mismatch protection
  6. Prints final inventory

NO terminal process is spawned. NO login is performed.
"""

from __future__ import annotations

import argparse
import sys
from uuid import UUID

from ..pool.terminal_pool import (
    StrategyPoolRegistry,
    StrategyMismatchError,
)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--master-id", required=True)
    p.add_argument("--strategy-id", required=True)
    p.add_argument("--strategy-key", required=True,
                   help="folder-safe key, e.g. low, pro, expert")
    args = p.parse_args()

    master_id = UUID(args.master_id)
    strategy_id = UUID(args.strategy_id)

    reg = StrategyPoolRegistry(
        master_id=master_id,
        strategy_id=strategy_id,
        strategy_key=args.strategy_key,
    )
    reg.load_from_db()

    print(f"[before prewarm] pools={len(reg.pools())} "
          f"active={len(reg.actives())} standby={len(reg.standbys())}")

    reg.ensure_prewarm()

    print(f"[after  prewarm] pools={len(reg.pools())} "
          f"active={len(reg.actives())} standby={len(reg.standbys())}")
    for p in reg.pools():
        print(f"  - {p.pool_name:20s} status={p.status:8s} "
              f"cap={p.capacity:3d} load={p.active_accounts_count:3d} "
              f"path={p.terminal_path}")

    chosen = reg.pick_active()
    print(f"[pick_active] chose {chosen.pool_name} (status={chosen.status})")

    # Cross-strategy guard demo
    other = UUID(int=strategy_id.int ^ 1)
    try:
        chosen.assert_strategy(other)
        print("[guard] ERROR: cross-strategy was NOT blocked")
        return 2
    except StrategyMismatchError as e:
        print(f"[guard] OK — cross-strategy blocked: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
