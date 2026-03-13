"""
MT5 Terminal Manager — main entry point.

Orchestrates:
  1. TerminalPool — pooled subprocess lifecycle (each terminal handles N accounts)
  2. TerminalAllocator — distributes accounts across terminals
  3. SessionManager — manages individual account sessions
  4. AutoProvisioner — auto-spawns terminals for new accounts
  5. ConnectionWatchdog — monitors heartbeats, triggers reconnects
  6. BalanceSync — persists balance updates to DB
  7. FailureHandler — marks failed accounts in DB
  8. HealthMonitor — CPU/memory/session monitoring

Usage:
  python -m mt5_manager.main

Architecture:
  ┌───────────────────────────────────────────────────────────────────────┐
  │                    MT5 Terminal Manager                               │
  │                                                                       │
  │  ┌──────────────────┐   ┌───────────────────┐                        │
  │  │ AutoProvisioner  │   │  SessionManager   │                        │
  │  │ (DB poll + Redis)│   │  (lifecycle mgmt) │                        │
  │  └────────┬─────────┘   └─────────┬─────────┘                        │
  │           │                       │                                    │
  │           ▼                       ▼                                    │
  │  ┌──────────────────────────────────────────────────┐                 │
  │  │              Terminal Allocator                    │                 │
  │  │  (strategy-affinity, least-loaded balancing)       │                 │
  │  └───────────────────────┬──────────────────────────┘                 │
  │                          │                                             │
  │                          ▼                                             │
  │  ┌──────────────────────────────────────────────────┐                 │
  │  │               Terminal Pool                       │                 │
  │  │                                                    │                 │
  │  │  ┌────────────┐ ┌────────────┐ ┌────────────┐    │                 │
  │  │  │ Terminal 1 │ │ Terminal 2 │ │ Terminal 3 │    │                 │
  │  │  │ 50 accts   │ │ 50 accts   │ │ 50 accts   │    │                 │
  │  │  └────────────┘ └────────────┘ └────────────┘    │                 │
  │  └──────────────────────────────────────────────────┘                 │
  │                                                                       │
  │  ┌──────────────┐ ┌────────────┐ ┌──────────────────┐                │
  │  │ BalanceSync  │ │ Watchdog   │ │ HealthMonitor    │                │
  │  └──────────────┘ └────────────┘ └──────────────────┘                │
  └───────────────────────────────────────────────────────────────────────┘
"""

import logging
import signal
import sys
import time
import json

from mt5_manager.config import get_manager_settings
from mt5_manager.terminal_pool import TerminalPool
from mt5_manager.terminal_allocator import TerminalAllocator
from mt5_manager.account_session import SessionManager
from mt5_manager.auto_provisioner import AutoProvisioner
from mt5_manager.watchdog import ConnectionWatchdog
from mt5_manager.balance_sync import BalanceSync, FailureHandler
from mt5_manager.health_monitor import HealthMonitor
from mt5_manager.credential_vault import decrypt_password

settings = get_manager_settings()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("mt5_manager.main")


def password_resolver(account_id: str) -> str:
    """Resolve decrypted password for an account."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session as DBSession

    engine = create_engine(settings.DATABASE_URL_SYNC)
    with DBSession(engine) as db:
        row = db.execute(text(
            "SELECT encrypted_password FROM mt5_accounts WHERE id = :id"
        ), {"id": account_id}).fetchone()

        if not row:
            raise ValueError(f"Account {account_id} not found")
        return decrypt_password(row.encrypted_password)


class MT5TerminalManager:
    """Main orchestrator for the MT5 Terminal Manager service."""

    def __init__(self):
        self.pool = TerminalPool()
        self.allocator = TerminalAllocator()
        self.session_manager = SessionManager()
        self.provisioner: AutoProvisioner | None = None
        self.watchdog: ConnectionWatchdog | None = None
        self.balance_sync: BalanceSync | None = None
        self.failure_handler: FailureHandler | None = None
        self.health_monitor: HealthMonitor | None = None

    def start(self):
        logger.info("=" * 70)
        logger.info("  CopyTrade Pro — MT5 Multi-Terminal Manager Starting")
        logger.info("=" * 70)
        logger.info(f"  Max terminals:        {settings.MAX_TERMINALS}")
        logger.info(f"  Accounts/terminal:    {settings.MAX_ACCOUNTS_PER_TERMINAL}")
        logger.info(f"  Total capacity:       {settings.MAX_TERMINALS * settings.MAX_ACCOUNTS_PER_TERMINAL}")
        logger.info(f"  Watchdog interval:    {settings.WATCHDOG_INTERVAL_S}s")
        logger.info(f"  Provision poll:       {settings.PROVISION_POLL_INTERVAL_S}s")
        logger.info(f"  Rebalance interval:   {settings.REBALANCE_INTERVAL_S}s")
        logger.info("=" * 70)

        # Load strategy → master mapping
        self._load_strategy_map()

        # 1. Pre-spawn initial terminal pool
        initial_terminals = max(1, settings.MAX_TERMINALS // 10)  # Start with 10% capacity
        for i in range(initial_terminals):
            terminal_id = self.pool.spawn_terminal()
            if terminal_id:
                self.allocator.register_terminal(terminal_id)
        logger.info(f"✓ Initial pool: {initial_terminals} terminals spawned")

        # 2. Start Balance Sync
        self.balance_sync = BalanceSync()
        self.balance_sync.start()
        logger.info("✓ Balance Sync started")

        # 3. Start Failure Handler
        self.failure_handler = FailureHandler()
        self.failure_handler.start()
        logger.info("✓ Failure Handler started")

        # 4. Start Auto Provisioner
        self.provisioner = AutoProvisioner(self.pool, self.allocator, self.session_manager)
        self.provisioner.start()
        logger.info("✓ Auto Provisioner started")

        # 5. Start Connection Watchdog
        self.watchdog = ConnectionWatchdog(self.pool, password_resolver)
        self.watchdog.start()
        logger.info("✓ Connection Watchdog started")

        # 6. Start Health Monitor
        self.health_monitor = HealthMonitor(self.pool, self.session_manager, self.allocator)
        self.health_monitor.start()
        logger.info("✓ Health Monitor started")

        logger.info("=" * 70)
        logger.info("  MT5 Multi-Terminal Manager is running")
        logger.info(f"  Capacity: {settings.MAX_TERMINALS * settings.MAX_ACCOUNTS_PER_TERMINAL} accounts")
        logger.info("=" * 70)

    def _load_strategy_map(self):
        """Load strategy → master account mapping from DB."""
        try:
            from sqlalchemy import create_engine, text
            from sqlalchemy.orm import Session as DBSession

            engine = create_engine(settings.DATABASE_URL_SYNC)
            with DBSession(engine) as db:
                rows = db.execute(text("""
                    SELECT s.name AS strategy_level, ma.id AS master_account_id
                    FROM strategies s
                    JOIN master_accounts ma ON ma.strategy_id = s.id
                    WHERE s.enabled = true
                """)).fetchall()

                mapping = {row.strategy_level: str(row.master_account_id) for row in rows}
                self.session_manager.update_strategy_map(mapping)
                logger.info(f"Loaded strategy map: {mapping}")
        except Exception as e:
            logger.warning(f"Could not load strategy map from DB: {e}")

    def status(self) -> dict:
        """Get comprehensive system status."""
        return {
            "pool": self.pool.get_pool_status(),
            "sessions": self.session_manager.get_session_summary(),
            "allocation": self.allocator.get_allocation_summary(),
            "health": self.health_monitor.get_health_report() if self.health_monitor else {},
        }

    def stop(self):
        logger.info("Shutting down MT5 Multi-Terminal Manager...")

        if self.provisioner:
            self.provisioner.stop()
        if self.watchdog:
            self.watchdog.stop()
        if self.health_monitor:
            self.health_monitor.stop()

        self.pool.stop_all()

        if self.balance_sync:
            self.balance_sync.stop()
        if self.failure_handler:
            self.failure_handler.stop()

        logger.info("MT5 Multi-Terminal Manager stopped.")


def main():
    manager = MT5TerminalManager()

    def shutdown(signum, frame):
        manager.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    manager.start()

    # Keep main thread alive and print status periodically
    try:
        while True:
            time.sleep(settings.HEALTH_REPORT_INTERVAL_S)
            status = manager.status()
            pool = status["pool"]
            sessions = status["sessions"]
            logger.info(
                f"Status: {pool['active']}/{pool['max']} terminals | "
                f"{pool['total_accounts']} accounts ({pool['utilization']} util) | "
                f"Sessions: {sessions['active']} active / {sessions['total']} total"
            )
    except KeyboardInterrupt:
        manager.stop()


if __name__ == "__main__":
    main()
