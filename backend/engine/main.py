"""
Copy Engine Orchestrator — main entry point.

Starts all engine components:
  1. MasterListener per active master account
  2. TradeDistributor (fan-out)
  3. ExecutionWorker per connected client (spawned as subprocesses)
  4. HealthMonitor
  5. ResultTracker

Usage:
  python -m engine.main

Architecture:
  ┌─────────────────────────────────────────────────────────────────┐
  │                        Copy Engine Service                      │
  │                                                                 │
  │  ┌──────────────┐    Redis pub/sub    ┌───────────────────┐    │
  │  │ MasterListener├──────────────────►│  TradeDistributor  │    │
  │  │  (per master) │                    │   (fan-out)        │    │
  │  └──────────────┘                    └────────┬──────────┘    │
  │                                               │                │
  │                          Redis queues (per client)             │
  │                    ┌──────────┬──────────┬─────┘               │
  │                    ▼          ▼          ▼                      │
  │              ┌──────────┐┌──────────┐┌──────────┐             │
  │              │ Executor ││ Executor ││ Executor │             │
  │              │ Worker 1 ││ Worker 2 ││ Worker N │             │
  │              └──────────┘└──────────┘└──────────┘             │
  │                                                                 │
  │  ┌───────────────┐  ┌────────────────┐                         │
  │  │ HealthMonitor │  │ ResultTracker  │                         │
  │  └───────────────┘  └────────────────┘                         │
  └─────────────────────────────────────────────────────────────────┘
"""

import logging
import signal
import sys
import time
import multiprocessing
from typing import List

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from cryptography.fernet import Fernet

from engine.config import get_engine_settings
from engine.master_listener import MasterListener
from engine.distributor import TradeDistributor
from engine.executor import ExecutionWorker
from engine.health_monitor import HealthMonitor
from engine.result_tracker import ResultTracker

settings = get_engine_settings()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("engine.main")

_fernet = Fernet(settings.MT5_CREDENTIAL_KEY.encode())


def decrypt(encrypted: str) -> str:
    return _fernet.decrypt(encrypted.encode()).decode()


def load_master_accounts(db_engine) -> list[dict]:
    """Load all active master accounts from the database."""
    with Session(db_engine) as db:
        rows = db.execute(text("""
            SELECT id, login, server FROM master_accounts
        """)).fetchall()
        # Master account passwords are stored in a secure vault / env vars
        # For now, we assume they're in a separate secure config
        return [{"id": str(r.id), "login": r.login, "server": r.server} for r in rows]


def load_client_accounts(db_engine) -> list[dict]:
    """Load all connected client MT5 accounts."""
    with Session(db_engine) as db:
        rows = db.execute(text("""
            SELECT id, login, encrypted_password, server
            FROM mt5_accounts
            WHERE status = 'connected'
        """)).fetchall()
        return [
            {
                "id": str(r.id),
                "login": r.login,
                "password": decrypt(r.encrypted_password),
                "server": r.server,
            }
            for r in rows
        ]


def run_executor_subprocess(client: dict):
    """Entry point for a client executor subprocess."""
    worker = ExecutionWorker(
        client_mt5_id=client["id"],
        login=client["login"],
        password=client["password"],
        server=client["server"],
    )
    worker.run()


class CopyEngine:
    """Orchestrates all engine components."""

    def __init__(self):
        self.db_engine = create_engine(settings.DATABASE_URL_SYNC)
        self.master_listeners: List[MasterListener] = []
        self.distributor: TradeDistributor | None = None
        self.health_monitor: HealthMonitor | None = None
        self.result_tracker: ResultTracker | None = None
        self.executor_processes: List[multiprocessing.Process] = []

    def start(self):
        logger.info("=" * 60)
        logger.info("  CopyTrade Pro — Copy Engine Starting")
        logger.info("=" * 60)

        # 1. Start Health Monitor
        self.health_monitor = HealthMonitor()
        self.health_monitor.start()
        logger.info("✓ Health Monitor started")

        # 2. Start Result Tracker
        self.result_tracker = ResultTracker()
        self.result_tracker.start()
        logger.info("✓ Result Tracker started")

        # 3. Start Trade Distributor
        self.distributor = TradeDistributor()
        self.distributor.start()
        logger.info("✓ Trade Distributor started")

        # 4. Start Master Listeners
        masters = load_master_accounts(self.db_engine)
        for master in masters:
            # Master passwords should come from a secure vault
            # This is a placeholder — in production use a KMS
            listener = MasterListener(
                master_account_id=master["id"],
                login=master["login"],
                password="master_password_from_vault",  # TODO: secure vault
                server=master["server"],
            )
            listener.start()
            self.master_listeners.append(listener)
        logger.info(f"✓ {len(masters)} Master Listeners started")

        # 5. Start Executor Workers (one subprocess per client)
        clients = load_client_accounts(self.db_engine)
        for client in clients:
            proc = multiprocessing.Process(
                target=run_executor_subprocess,
                args=(client,),
                name=f"Executor-{client['login']}",
                daemon=True,
            )
            proc.start()
            self.executor_processes.append(proc)
        logger.info(f"✓ {len(clients)} Execution Workers started")

        logger.info("=" * 60)
        logger.info(f"  Engine running: {len(masters)} masters → {len(clients)} clients")
        logger.info("=" * 60)

    def stop(self):
        logger.info("Shutting down Copy Engine...")

        for listener in self.master_listeners:
            listener.stop()

        if self.distributor:
            self.distributor.stop()

        for proc in self.executor_processes:
            proc.terminate()
            proc.join(timeout=5)

        if self.health_monitor:
            self.health_monitor.stop()

        if self.result_tracker:
            self.result_tracker.stop()

        logger.info("Copy Engine stopped.")


def main():
    engine = CopyEngine()

    def shutdown_handler(signum, frame):
        engine.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    engine.start()

    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        engine.stop()


if __name__ == "__main__":
    main()
