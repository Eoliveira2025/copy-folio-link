# CopyTrade Pro V2 — Pool-based Agent

Independent, pool-based MT5 execution engine. Runs **alongside** V1
(`backend/agent/`) without touching it.

## Isolation guarantees

- Module: `backend/agent_v2/` only. V1 code is never imported.
- Redis: separate DB (`/2`) and mandatory key prefix `copytrade_v2:`.
- Postgres: separate tables (`pool_terminal`, `account_terminal_map`,
  `v2_orders`, `strategy_change_requests`).
- Windows paths: `C:\copytrade_v2`, `C:\MT5_Pool_V2`, `C:\MT5_Masters_V2`,
  `C:\copytrade_v2_logs`.
- Env vars: `V2_*` prefix.
- Metrics port: 9091 (V1 keeps 9090).

## Architecture (segmented pools)

Pools are bound to `(master_id, strategy_id)`. A LOW client never lands in
a PRO pool. When `pool_low_01` reaches `POOL_CAPACITY`, the system
promotes a pre-warmed `pool_low_02` (STANDBY → ACTIVE) and provisions a
new STANDBY in the background.

See the project plan for the full design (states, reconciler rules,
strategy transition flow).

## Status

Increment 1: skeleton + config + logger + migration 015.
