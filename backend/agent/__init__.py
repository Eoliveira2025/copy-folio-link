"""
CopyTrade Pro — Windows VPS Copy Agent
=======================================

Standalone agent that runs on a Windows VPS with MetaTrader 5 installed.
Combines the Copy Engine (master monitoring + trade distribution + execution)
with the MT5 Terminal Manager (multi-account management).

Connects to the remote Ubuntu server's PostgreSQL and Redis.

Usage:
  python -m agent.main

Architecture:
  ┌─────────────────────────────────────────────────────────────────┐
  │                    Windows VPS Agent                             │
  │                                                                 │
  │  ┌─────────────────────────────────────────────────────────┐   │
  │  │  COPY ENGINE                                             │   │
  │  │  ┌──────────────┐     ┌───────────────┐                 │   │
  │  │  │MasterListener│────►│ Distributor   │                 │   │
  │  │  │ (per master) │     │ (fan-out)     │                 │   │
  │  │  └──────────────┘     └──────┬────────┘                 │   │
  │  │                              │                           │   │
  │  │          ┌───────────────────┼────────────────┐         │   │
  │  │          ▼                   ▼                ▼         │   │
  │  │   ┌───────────┐      ┌───────────┐    ┌───────────┐   │   │
  │  │   │ Executor  │      │ Executor  │    │ Executor  │   │   │
  │  │   │ Worker 1  │      │ Worker 2  │    │ Worker N  │   │   │
  │  │   └───────────┘      └───────────┘    └───────────┘   │   │
  │  │                                                         │   │
  │  │  ResultTracker ← persists to PostgreSQL                 │   │
  │  │  HealthMonitor ← publishes to Redis                     │   │
  │  │  MetricsPublisher ← Prometheus :9090                    │   │
  │  └─────────────────────────────────────────────────────────┘   │
  │                                                                 │
  │  ┌─────────────────────────────────────────────────────────┐   │
  │  │  DB SYNC (periodic refresh)                              │   │
  │  │  - New master accounts                                   │   │
  │  │  - New/removed client accounts                           │   │
  │  │  - Strategy changes                                      │   │
  │  │  - Balance updates                                       │   │
  │  └─────────────────────────────────────────────────────────┘   │
  │                                                                 │
  │  Remote: PostgreSQL + Redis on Ubuntu (91.98.20.163)           │
  └─────────────────────────────────────────────────────────────────┘

Requirements:
  - Windows Server 2022 with Python 3.12
  - MetaTrader 5 installed (terminal64.exe)
  - pip install -r requirements-agent.txt
"""
