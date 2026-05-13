# Institutional MT5 Gateway V2 Architecture

## Overview
The V2 architecture uses a **Virtual Institutional Gateway** model. 
Contrary to the initial multi-account assumption, MetaTrader 5 supports only one active account session per process. 

To achieve professional-grade scaling and isolation, V2 implements a **1-Terminal-Per-Account** model, grouped and managed by **Execution Pools**.

## Components

### 1. TerminalAllocatorV2
Responsible for distributing accounts to dedicated terminal instances.
- Guarantees `strategy_id` isolation at the hardware/process level.
- Ensures a 1:1 mapping between `mt5_account` and `terminal_process`.

### 2. PooledTerminalProcess
Wraps a single `terminal64.exe` instance.
- Runs in `/portable` mode.
- Managed via OS PIDs.
- Automatically restarted by `HealthMonitor` if it crashes.

### 3. StrategyRouter
The central safety gate for all execution requests.
- **Strict Strategy Isolation**: Rejects orders if `master_strategy_id` != `client_strategy_id`.
- Prevents "cross-contamination" where a LOW risk client receives a HIGH risk order.

### 4. AccountSession
Handles the serialized login and command execution for the terminal.
- Only one session exists per terminal.
- Holds a lock during execution to prevent race conditions.

## Safety & Security
- **LIVE_WHITELIST**: Real accounts are blocked unless explicitly whitelisted in `v2_account_flags`.
- **Strategy Guard**: Hard-coded checks in the Router and Repository layers.
- **Process Isolation**: If one MT5 terminal hangs, it only affects one client account.

## Database Schema
- `pool_terminal`: Metadata for each MT5 installation/folder.
- `account_terminal_map`: 1:1 mapping of account to terminal.
- `v2_orders`: High-performance audit log for all V2 trades.
