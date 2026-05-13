"""End-to-end smoke for wiring + distributor V2 in DRY_RUN.

Path: master event payload → DistributorV2.handle_event → allocator
→ PoolWorker.queue → AccountSession (dry-run) → OrderExecutor (blocked
by safety guard since DRY_RUN) → task simulated as DONE.

NO Redis required: we call distributor.handle_event(payload) directly.
NO DB required: repo + AutoProvisioner are monkey-patched in-memory.
NO MT5 required: DRY_RUN guard short-circuits before mt5 import.
"""

from __future__ import annotations

import os
import time
from uuid import uuid4

# Safe defaults
os.environ["V2_EXECUTION_MODE"] = "DRY_RUN"
os.environ["V2_ORDER_EXECUTION_ENABLED"] = "false"
os.environ["V2_SESSION_DRY_RUN"] = "true"
os.environ["V2_POOL_CAPACITY"] = "5"
os.environ["V2_POOL_PREWARM_STANDBY"] = "1"
os.environ["V2_POOL_AUTOPROVISION_ENABLED"] = "true"
os.environ["V2_SESSION_STICKY_HOLD_MS"] = "0"

from agent_v2.config import get_v2_settings  # noqa: E402
get_v2_settings.cache_clear()

# Patch repo + provisioner with the same in-memory fakes from smoke_allocator
from agent_v2.pool import repo, auto_provisioner as ap_mod  # noqa: E402

_POOLS: dict = {}; _LOADS: dict = {}; _MAPS: dict = {}

def _list_pools(sid): return [p for p in _POOLS.values() if p.strategy_id == sid]
def _ins_pool(*, pool_name, master_id, strategy_id, terminal_path,
              capacity, status="STANDBY", host=None):
    pid = uuid4()
    row = repo.PoolRow(id=pid, pool_name=pool_name, master_id=master_id,
                       strategy_id=strategy_id, terminal_path=terminal_path,
                       capacity=capacity, current_load=0, status=status, host=host)
    _POOLS[pid] = row; _LOADS[pid] = 0
    return row
def _upd_status(pid, status):
    p = _POOLS[pid]
    _POOLS[pid] = repo.PoolRow(**{**p.__dict__, "status": status})
def _count(pid): return _LOADS.get(pid, 0)
def _get_map(aid): return _MAPS.get(aid)
def _ins_map(*, account_id, pool_id, terminal_id, master_id, strategy_id):
    row = repo.AccountMappingRow(account_id=account_id, pool_id=pool_id,
                                 terminal_id=terminal_id, master_id=master_id,
                                 strategy_id=strategy_id)
    _MAPS[account_id] = row; _LOADS[pool_id] = _LOADS.get(pool_id, 0) + 1
    return row
def _del_map(aid):
    row = _MAPS.pop(aid, None)
    if row: _LOADS[row.pool_id] = max(0, _LOADS.get(row.pool_id, 0) - 1)

repo.list_pools_for_strategy = _list_pools
repo.insert_pool = _ins_pool
repo.update_pool_status = _upd_status
repo.count_pool_accounts = _count
repo.get_account_mapping = _get_map
repo.insert_account_mapping = _ins_map
repo.delete_account_mapping = _del_map
ap_mod.AutoProvisioner._create_folder_skeleton = lambda self, p: None


from agent_v2.pool.allocator import TerminalAllocator  # noqa: E402
from agent_v2.wiring import PoolWorkerRegistry  # noqa: E402
from agent_v2.distributor import DistributorV2, ClientAccount  # noqa: E402


def main() -> int:
    master = uuid4()
    strategy = uuid4()
    alloc = TerminalAllocator(strategy_key_resolver=lambda sid: "low")
    workers = PoolWorkerRegistry()

    # Three V2 client accounts, all ACTIVE on this strategy
    clients = [ClientAccount(account_id=uuid4(), login=1000 + i,
                             account_type="demo", state="ACTIVE")
               for i in range(3)]

    def _resolve_clients(m, s):
        assert m == master and s == strategy
        return clients

    dist = DistributorV2(
        allocator=alloc, worker_registry=workers,
        client_resolver=_resolve_clients,
    )

    # Pre-create workers as accounts get assigned. The distributor calls
    # workers.get(pool_id); we hook a shim that builds workers lazily.
    real_get = workers.get
    def _get_or_build(pool_id):
        w = real_get(pool_id)
        if w: return w
        # Find pool object via allocator's registry
        for reg in alloc._registries.values():
            for p in reg.pools():
                if p.id == pool_id:
                    return workers.get_or_create(
                        p,
                        account_login_resolver=lambda aid: next(
                            c.login for c in clients if c.account_id == aid),
                        account_type_resolver=lambda aid: "demo",
                    )
        return None
    workers.get = _get_or_build  # type: ignore

    # Simulate a master OPEN event
    payload_open = {
        "event": "OPEN", "master_id": str(master), "strategy_id": str(strategy),
        "master_ticket": 9001, "symbol": "EURUSD", "side": "BUY",
        "volume": 0.10, "price": 1.10, "magic": 42,
    }
    summary = dist.handle_event(payload_open)
    print(f"[OK] OPEN distributed: {summary}")
    assert summary["submitted"] == 3, summary

    # Wait for workers to drain
    time.sleep(0.8)
    for w in workers.all():
        assert w.queue.depth() == 0, f"queue not drained: {w.pool.pool_name}"
    print(f"[OK] all queues drained; workers={len(workers.all())}")

    # CLOSE event — only ACTIVE+EXIT_ONLY accept
    payload_close = {
        "event": "CLOSE", "master_id": str(master),
        "strategy_id": str(strategy), "master_ticket": 9001,
        "symbol": "EURUSD",
    }
    summary = dist.handle_event(payload_close)
    print(f"[OK] CLOSE distributed: {summary}")
    assert summary["submitted"] == 3

    # State gate — flip one client to PENDING_STRATEGY_CHANGE; OPEN should skip
    clients[0].state = "PENDING_STRATEGY_CHANGE"
    summary = dist.handle_event(payload_open)
    print(f"[OK] OPEN with one paused: {summary}")
    assert summary["submitted"] == 2 and summary["skipped"] == 1

    # EXIT_ONLY accepts CLOSE but not OPEN
    clients[0].state = "EXIT_ONLY"
    s_open = dist.handle_event(payload_open)
    s_close = dist.handle_event(payload_close)
    assert s_open["submitted"] == 2, s_open
    assert s_close["submitted"] == 3, s_close
    print(f"[OK] EXIT_ONLY gate: open={s_open}, close={s_close}")

    workers.stop_all()
    print("\nAll wiring/distributor smoke tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
