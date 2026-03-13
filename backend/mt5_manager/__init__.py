"""
MT5 Terminal Manager — manages multiple MT5 terminal instances on VPS servers.

Since the MetaTrader5 Python API only supports ONE connection per process,
this service spawns separate subprocesses for each MT5 account (master or client).

Architecture:
  ┌─────────────────────────────────────────────────────────────────────┐
  │                    MT5 Terminal Manager                             │
  │                                                                     │
  │  ┌──────────────────┐                                               │
  │  │  TerminalPool    │  Manages lifecycle of all MT5 subprocesses    │
  │  │  (orchestrator)  │                                               │
  │  └────────┬─────────┘                                               │
  │           │                                                         │
  │    ┌──────┴──────┬──────────────┬──────────────┐                   │
  │    ▼             ▼              ▼              ▼                    │
  │  ┌──────┐  ┌──────┐  ┌──────────┐  ┌──────────┐                  │
  │  │Proc 1│  │Proc 2│  │ Proc 3   │  │ Proc N   │                  │
  │  │MT5   │  │MT5   │  │ MT5      │  │ MT5      │                  │
  │  │Login │  │Login │  │ Login    │  │ Login    │                  │
  │  │12345 │  │67890 │  │ 11111    │  │ NNNNN    │                  │
  │  └──────┘  └──────┘  └──────────┘  └──────────┘                  │
  │                                                                     │
  │  ┌──────────────────┐  ┌──────────────────────┐                    │
  │  │ AutoProvisioner  │  │ ConnectionWatchdog   │                    │
  │  │ (new accounts)   │  │ (reconnect stale)    │                    │
  │  └──────────────────┘  └──────────────────────┘                    │
  │                                                                     │
  │  Communication: Redis command/response queues per process           │
  └─────────────────────────────────────────────────────────────────────┘

Run: python -m mt5_manager.main
"""
