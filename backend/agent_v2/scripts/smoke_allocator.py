"""Smoke test for TerminalAllocator — strategy-segmented assignment.

Validates:
  * 20 LOW accounts with capacity=15 → 15 in pool_low_01, 5 in pool_low_02
    (STANDBY auto-promoted, refilled in background)
  * 10 PRO accounts → all in pool_pro_01 (separate registry)
  * Cross-strategy attempt: assigning a LOW account against PRO master/strategy
    of an already-mapped account raises StrategyMismatchError
  * Assignment of NEW LOW account against PRO pool's strategy is impossible
    because allocator routes via (master_id, strategy_id) registry — pools
    never mix.

Runs with NO DB and NO MT5 by monkey-patching repo and provisioner with
in-memory fakes.

Usage:
    python -m agent_v2.scripts.smoke_allocator
"""

from __future__ import annotations

import os
from uuid import UUID, uuid4

# Force a deterministic capacity BEFORE settings are cached
os.environ["V2_POOL_CAPACITY"] = "15"
os.environ["V2_POOL_PREWARM_STANDBY"] = "1"
os.environ["V2_POOL_AUTOPROVISION_ENABLED"] = "true"

from agent_v2.config import get_v2_settings  # noqa: E402
get_v2_settings.cache_clear()

from agent_v2.pool import repo  # noqa: E402
from agent_v2.pool import auto_provisioner as ap_mod  # noqa: E402
from agent_v2.pool.terminal_pool import StrategyMismatchError  # noqa: E402


# ─────────────────────────────────────────────────────────────────
# In-memory fakes (replace DB + filesystem)
# ─────────────────────────────────────────────────────────────────
_POOLS: dict[UUID, repo.PoolRow] = {}
_LOADS: dict[UUID, int] = {}
_MAPS: dict[UUID, repo.AccountMappingRow] = {}


def _fake_list_pools_for_strategy(strategy_id):
    return [p for p in _POOLS.values() if p.strategy_id == strategy_id]


def _fake_get_pool_by_name(pool_name):
    for p in _POOLS.values():
        if p.pool_name == pool_name:
            return p
    return None


def _fake_insert_pool(*, pool_name, master_id, strategy_id, terminal_path,
                     capacity, status="STANDBY", host=None):
    pid = uuid4()
    row = repo.PoolRow(
        id=pid, pool_name=pool_name, master_id=master_id,
        strategy_id=strategy_id, terminal_path=terminal_path,
        capacity=capacity, current_load=0, status=status, host=host,
    )
    _POOLS[pid] = row
    _LOADS[pid] = 0
    return row


def _fake_update_pool_status(pool_id, status):
    p = _POOLS[pool_id]
    _POOLS[pool_id] = repo.PoolRow(
        **{**p.__dict__, "status": status}
    )


def _fake_count_pool_accounts(pool_id):
    return _LOADS.get(pool_id, 0)


def _fake_get_account_mapping(account_id):
    return _MAPS.get(account_id)


def _fake_insert_account_mapping(*, account_id, pool_id, terminal_id,
                                master_id, strategy_id):
    row = repo.AccountMappingRow(
        account_id=account_id, pool_id=pool_id, terminal_id=terminal_id,
        master_id=master_id, strategy_id=strategy_id,
    )
    _MAPS[account_id] = row
    _LOADS[pool_id] = _LOADS.get(pool_id, 0) + 1
    return row


def _fake_delete_account_mapping(account_id):
    row = _MAPS.pop(account_id, None)
    if row:
        _LOADS[row.pool_id] = max(0, _LOADS.get(row.pool_id, 0) - 1)


def _patch_repo():
    repo.list_pools_for_strategy = _fake_list_pools_for_strategy
    repo.get_pool_by_name = _fake_get_pool_by_name
    repo.insert_pool = _fake_insert_pool
    repo.update_pool_status = _fake_update_pool_status
    repo.count_pool_accounts = _fake_count_pool_accounts
    repo.get_account_mapping = _fake_get_account_mapping
    repo.insert_account_mapping = _fake_insert_account_mapping
    repo.delete_account_mapping = _fake_delete_account_mapping


def _patch_provisioner_fs():
    # Skip filesystem creation entirely
    ap_mod.AutoProvisioner._create_folder_skeleton = lambda self, p: None


_patch_repo()
_patch_provisioner_fs()

# Import allocator AFTER patching so it picks up the fake repo bindings
from agent_v2.pool.allocator import TerminalAllocator  # noqa: E402


# ─────────────────────────────────────────────────────────────────
# Test
# ─────────────────────────────────────────────────────────────────
def main() -> int:
    master_low = uuid4()
    master_pro = uuid4()
    strat_low = uuid4()
    strat_pro = uuid4()

    key_map = {strat_low: "low", strat_pro: "pro"}
    alloc = TerminalAllocator(strategy_key_resolver=lambda sid: key_map[sid])

    # ── 20 LOW accounts ──────────────────────────────────────────
    low_accounts = [uuid4() for _ in range(20)]
    pool_counts: dict[str, int] = {}
    for aid in low_accounts:
        a = alloc.assign(account_id=aid, master_id=master_low,
                         strategy_id=strat_low)
        pool_counts[a.pool_name] = pool_counts.get(a.pool_name, 0) + 1

    print("LOW distribution:", pool_counts)
    assert pool_counts.get("pool_low_01") == 15, \
        f"expected 15 in pool_low_01, got {pool_counts.get('pool_low_01')}"
    assert pool_counts.get("pool_low_02") == 5, \
        f"expected 5 in pool_low_02, got {pool_counts.get('pool_low_02')}"

    # ── 10 PRO accounts ──────────────────────────────────────────
    pro_accounts = [uuid4() for _ in range(10)]
    pro_counts: dict[str, int] = {}
    for aid in pro_accounts:
        a = alloc.assign(account_id=aid, master_id=master_pro,
                         strategy_id=strat_pro)
        pro_counts[a.pool_name] = pro_counts.get(a.pool_name, 0) + 1

    print("PRO distribution:", pro_counts)
    assert pro_counts == {"pool_pro_01": 10}, \
        f"expected 10 in pool_pro_01 only, got {pro_counts}"

    # ── Cross-strategy guard: re-map an existing LOW acct to PRO ──
    blocked = False
    try:
        alloc.assign(account_id=low_accounts[0],
                     master_id=master_pro, strategy_id=strat_pro)
    except StrategyMismatchError as e:
        blocked = True
        print(f"cross-strategy correctly blocked: {e}")
    assert blocked, "cross-strategy remap MUST raise StrategyMismatchError"

    # ── Verify pool isolation: no LOW pool serves PRO and vice versa ──
    for p in _POOLS.values():
        for m in _MAPS.values():
            if m.pool_id == p.id:
                assert m.strategy_id == p.strategy_id, \
                    f"pool {p.pool_name} mixed strategies!"
                assert m.master_id == p.master_id, \
                    f"pool {p.pool_name} mixed masters!"

    # ── Sticky reuse ─────────────────────────────────────────────
    again = alloc.assign(account_id=low_accounts[0],
                         master_id=master_low, strategy_id=strat_low)
    assert again.reused, "second assign of same account must reuse mapping"
    print(f"sticky reuse OK for {low_accounts[0]} -> pool_id={again.pool_id}")

    print("\nAll allocator assertions passed.")
    print(f"Pools created: {len(_POOLS)}")
    for p in _POOLS.values():
        print(f"  {p.pool_name:15s} status={p.status:8s} "
              f"load={_LOADS[p.id]:>2}/{p.capacity} "
              f"strategy={key_map[p.strategy_id]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
