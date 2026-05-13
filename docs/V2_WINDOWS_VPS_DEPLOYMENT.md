# ── V2_WINDOWS_VPS_DEPLOYMENT.md ───────────────────────

# CopyTrade Pro V2: Institutional Windows VPS Deployment Guide

This document describes the process of installing and running the V2 Institutional Executor on a dedicated Windows VPS.

## 1. Prerequisites

### Windows VPS Requirements
- **OS**: Windows Server 2019/2022 recommended.
- **Hardware**: Dedicated resources (no sharing with V1).
- **Network**: Low latency to the Linux Backend (Postgres/Redis) and MT5 Broker servers.

### Software Stack
- **Python**: 3.10+ (Add to PATH during installation).
- **Git**: For pulling updates (optional, can use ZIP).
- **MetaTrader 5**: Installed at `C:\Program Files\MetaTrader 5`.

## 2. Installation Steps

### Step 1: Create Folder Structure
Run the installation script to create isolated folders:
`C:\copytrade_v2`
`C:\MT5_Pool_V2`
`C:\MT5_Masters_V2`
`C:\copytrade_v2_logs`

### Step 2: Virtual Environment
```powershell
cd C:\copytrade_v2
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

### Step 3: Configure Environment
Copy `.env.production.example` to `.env` and fill the variables:
- `V2_DATABASE_URL_SYNC`: Linux Postgres URL.
- `V2_REDIS_URL`: Linux Redis URL (DB /2).
- `V2_MT5_CREDENTIAL_KEY`: 32-byte Base64 key for account encryption.

### Step 4: Pre-flight Checks
Run the pre-flight test to validate connectivity and configuration:
```powershell
python backend/agent_v2/tests/run_final_v2_preflight.py
```

## 3. Operational Scripts

Located in the `scripts/` folder:
- `install_v2_windows_vps.ps1`: Automated initial setup.
- `start_v2_executor.ps1`: Starts the V2 Master Monitor and pool.
- `stop_v2_executor_safe.ps1`: Stops all V2 processes safely.
- `health_check_v2.ps1`: Quick status check of V2.
- `open_vps_monitor.ps1`: Opens the local V2 dashboard.

## 4. Maintenance

### Monitoring
Check logs at `C:\copytrade_v2_logs`.
The local monitor is available at `http://localhost:8000` (or configured port).

### Scaling
Adjust `V2_POOL_CAPACITY` in `.env` to increase density (default 15, max recommended 50 per terminal).

## 5. Security & Isolation
- V2 uses Redis DB /2. **Never** use DB /0 or /1 (reserved for V1/Shared).
- V2 processes do not kill `terminal64.exe` instances unless they belong to `C:\MT5_Pool_V2`.
- All environment variables are prefixed with `V2_`.
