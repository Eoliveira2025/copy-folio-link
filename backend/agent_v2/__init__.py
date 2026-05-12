"""CopyTrade Pro V2 — Pool-based MT5 execution engine.

Strict isolation from V1 (`backend/agent/`):
  * Separate Redis DB and prefix `copytrade_v2:*`
  * Separate tables (`pool_terminal`, `account_terminal_map`, `v2_orders`, ...)
  * Separate Windows paths (`C:\\copytrade_v2`, `C:\\MT5_Pool_V2`, ...)
  * Pools segmented per (master_id, strategy_id) — no cross-strategy mixing.
"""
