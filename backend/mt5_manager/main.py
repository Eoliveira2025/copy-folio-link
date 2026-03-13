"""
MT5 Terminal Manager — main entry point.

Orchestrates:
  1. TerminalPool — subprocess lifecycle
  2. AutoProvisioner — auto-spawns terminals for new accounts
  3. ConnectionWatchdog — monitors heartbeats, triggers reconnects
  4. BalanceSync — persists balance updates to DB
  5. FailureHandler — marks failed accounts in DB

Usage:
  python -m mt5_manager.main

Architecture:
  ┌───────────────────────────────────────────────────────────────┐
  │                   MT5 Terminal Manager                         │
  │                                                               │
  │  ┌────────────────┐  ┌──────────────────┐                    │
  │  │ AutoProvisioner│  │  Watchdog        │                    │
  │  │ (spawn new)    │  │  (reconnect)     │                    │
  │  └───────┬────────┘  └────────┬─────────┘                    │
  │          │                    │                                │
  │          ▼                    ▼                                │
  │  ┌──────────────────────────────────────┐                    │
  │  │           Terminal Pool              │                    │
  │  │                                      │                    │
  │  │  ┌──────┐ ┌──────┐ ┌──────┐ ┌─────┐│                    │
  │  │  │MT5   │ │MT5   │ │MT5   │ │ ... ││                    │
  │  │  │12345 │ │67890 │ │11111 │ │     ││                    │
  │  │  └──────┘ └──────┘ └──────┘ └─────┘│                    │
  │  └──────────────────────────────────────┘                    │
  │                                                               │
  │  ┌───────────────┐  ┌──────────────────┐                     │
  │  │ BalanceSync   │  │ FailureHandler   │                     │
  │  └───────────────┘  └──────────────────┘                     │
  └───────────────────────────────────────────────────────────────┘
"""

import logging
import signal
import sys
import time

from mt5_manager.config import get_manager_settings
from mt5_manager.terminal_pool import TerminalPool
from mt5_manager.auto_provisioner import AutoProvisioner
from mt5_manager.watchdog import ConnectionWatchdog
from mt5_manager.balance_sync import BalanceSync, FailureHandler
from mt5_manager.credential_vault import decrypt_password

settings = get_manager_settings()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("mt5_manager.main")


def password_resolver(account_id: str) -> str:
    """Resolve decrypted password for an account (used by watchdog for restarts)."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session

    engine = create_engine(settings.DATABASE_URL_SYNC)
    with Session(engine) as db:
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
        self.provisioner: AutoProvisioner | None = None
        self.watchdog: ConnectionWatchdog | None = None
        self.balance_sync: BalanceSync | None = None
        self.failure_handler: FailureHandler | None = None

    def start(self):
        logger.info("=" * 60)
        logger.info("  CopyTrade Pro — MT5 Terminal Manager Starting")
        logger.info("=" * 60)
        logger.info(f"  Max terminals: {settings.MAX_TERMINALS}")
        logger.info(f"  Watchdog interval: {settings.WATCHDOG_INTERVAL_S}s")
        logger.info(f"  Provision poll: {settings.PROVISION_POLL_INTERVAL_S}s")
        logger.info("=" * 60)

        # 1. Start Balance Sync
        self.balance_sync = BalanceSync()
        self.balance_sync.start()
        logger.info("✓ Balance Sync started")

        # 2. Start Failure Handler
        self.failure_handler = FailureHandler()
        self.failure_handler.start()
        logger.info("✓ Failure Handler started")

        # 3. Start Auto Provisioner (spawns terminals for existing accounts)
        self.provisioner = AutoProvisioner(self.pool)
        self.provisioner.start()
        logger.info("✓ Auto Provisioner started")

        # 4. Start Connection Watchdog
        self.watchdog = ConnectionWatchdog(self.pool, password_resolver)
        self.watchdog.start()
        logger.info("✓ Connection Watchdog started")

        logger.info("=" * 60)
        logger.info("  MT5 Terminal Manager is running")
        logger.info("  Terminals will be auto-provisioned from the database")
        logger.info("=" * 60)

    def status(self) -> dict:
        """Get current pool status."""
        return self.pool.get_pool_status()

    def stop(self):
        logger.info("Shutting down MT5 Terminal Manager...")

        if self.provisioner:
            self.provisioner.stop()

        if self.watchdog:
            self.watchdog.stop()

        self.pool.stop_all()

        if self.balance_sync:
            self.balance_sync.stop()

        if self.failure_handler:
            self.failure_handler.stop()

        logger.info("MT5 Terminal Manager stopped.")


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
            logger.info(
                f"Pool status: {status['active']}/{status['max']} terminals active | "
                f"States: {status['by_state']}"
            )
    except KeyboardInterrupt:
        manager.stop()


if __name__ == "__main__":
    main()
