# V2 Institutional Operational Hardening Guide

This document outlines the operational measures implemented to ensure maximum stability, density, and ease of support for the V2 Institutional MT5 system.

## 1. Operational Hardening Measures

### 1.1 Process Management
- **Isolation**: Each account runs in its own `/portable` directory inside `C:\MT5_Pool_V2\instances\{account_id}`.
- **Liveness Checks**: The `HealthMonitor` checks process existence every 15s via `psutil`.
- **MT5 Freeze Detection**: Automated detection of high CPU/RAM usage. If a terminal exceeds 800MB RAM, it is automatically "recycled" (restarted).
- **Restart Limits**: Terminals are limited to 10 restarts per hour to prevent crash loops.

### 1.2 Resource Optimization
- **Cleanup Service**: `AccountCleanupService` automatically removes orphaned instance folders and old log files (>3 days).
- **Footprint**: Terminals run in background (headless mode whenever possible) to minimize GPU/UI overhead.
- **Redis Locks**: All session acquisitions use `DistributedLock` with short TTLs to prevent deadlocks.

## 2. Self-Healing
- **Auto-Recovery**: If a terminal crashes, it is restarted immediately.
- **Recycle Logic**: Periodic recycling of long-running terminals ensures memory leaks don't accumulate.
- **Safe Mode**: The system enters `SAFE_MODE` if VPS resources (CPU/RAM) exceed critical thresholds, preventing new order executions until stabilized.

## 3. Operational Dashboard
The local monitor (`institutional_ui.py`) provides:
- **Quick Actions**: Reconnect, Recycle, Safe Remove (checks positions first), Force Remove.
- **Real-time Metrics**: Stability Score, Avg Latency, RAM/CPU per terminal, Recycle counts.
- **Capacity Score**: Real-time evaluation of how many more accounts the VPS can handle safely.

## 4. Support Tools
- **Support Helper CLI**: `python -m backend.agent_v2.tools.support_helper logs {account_id}` for instant log access.
- **Human-Readable Logs**: Enhanced logs include `PID`, `account_id`, `strategy`, and `reason` for every action.

## 5. Deployment Recommendation
- **Rollout Phase 1**: 5-10 accounts, monitor `Stability Score` for 24h.
- **Rollout Phase 2**: 30 accounts, check `VPS Capacity`.
- **Full Scale**: Up to 100 accounts per VPS (depending on hardware).

---
*Target: 99.9% Operational Uptime | Zero Manual Maintenance*
