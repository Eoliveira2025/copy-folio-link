"""
CopyTrade Pro — Windows VPS Copy Agent
=======================================

Main entry point. Orchestrates all components:
  1. DBSynchronizer — polls PostgreSQL for account changes
  2. MasterMonitor — one subprocess per master account (10ms polling)
  3. TradeDistributor — fans out trade events to client queues
  4. ExecutionWorker — one subprocess per client account
  5. ResultTracker — persists results to PostgreSQL

Usage:
  cd backend
  python -m agent.main

Requires:
  - Windows Server with Python 3.12 and MetaTrader 5
  - .env file with DATABASE_URL_SYNC, REDIS_URL, MT5_CREDENTIAL_KEY
"""

import logging
import signal
import sys
import time
import multiprocessing
from typing import Dict, Set

from agent.config import get_agent_settings
from agent.db_sync import DBSynchronizer, MasterInfo, ClientInfo
from agent.master_monitor import master_listener_process
from agent.distributor import TradeDistributor
from agent.executor import executor_process
from agent.result_tracker import ResultTracker

settings = get_agent_settings()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("agent.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("agent.main")


class CopyAgent:
    """
    Main orchestrator for the Windows VPS Copy Agent.

    Lifecycle:
      1. Start DB synchronizer
      2. Spawn master listeners for all active masters
      3. Start trade distributor
      4. Spawn execution workers for all connected clients
      5. Start result tracker
      6. Periodically sync with DB for new accounts/changes
    """

    def __init__(self):
        self.master_processes: Dict[str, multiprocessing.Process] = {}
        self.client_processes: Dict[str, multiprocessing.Process] = {}
        self.distributor: TradeDistributor | None = None
        self.result_tracker: ResultTracker | None = None
        self.db_sync: DBSynchronizer | None = None
        self._running = False

    def start(self):
        logger.info("=" * 70)
        logger.info("  CopyTrade Pro — Windows VPS Copy Agent")
        logger.info("=" * 70)
        logger.info(f"  Database:      {settings.DATABASE_URL_SYNC.split('@')[1] if '@' in settings.DATABASE_URL_SYNC else 'local'}")
        logger.info(f"  Redis:         {settings.REDIS_URL.split('@')[1] if '@' in settings.REDIS_URL else settings.REDIS_URL}")
        logger.info(f"  MT5 Terminal:  {settings.MT5_TERMINAL_PATH}")
        logger.info(f"  Poll interval: {settings.MASTER_POLL_INTERVAL_MS}ms")
        logger.info(f"  Max slippage:  {settings.MAX_SLIPPAGE_POINTS} points")
        logger.info(f"  DB sync:       every {settings.DB_SYNC_INTERVAL_S}s")
        logger.info("=" * 70)

        self._running = True

        # 1. DB Synchronizer
        self.db_sync = DBSynchronizer(
            on_masters_changed=self._on_masters_changed,
            on_clients_changed=self._on_clients_changed,
        )
        self.db_sync.start()
        # Wait for initial load
        time.sleep(2)
        logger.info("✓ DB Synchronizer started")

        # 2. Result Tracker
        self.result_tracker = ResultTracker()
        self.result_tracker.start()
        logger.info("✓ Result Tracker started")

        # 3. Trade Distributor
        self.distributor = TradeDistributor()
        self.distributor.start()
        logger.info("✓ Trade Distributor started")

        # 4. Spawn master listeners
        for master_id, master in self.db_sync.masters.items():
            self._spawn_master_listener(master_id, master)
        logger.info(f"✓ {len(self.master_processes)} Master Listeners started")

        # 5. Spawn execution workers
        for client_id, client in self.db_sync.clients.items():
            self._spawn_executor(client_id, client)
        logger.info(f"✓ {len(self.client_processes)} Execution Workers started")

        logger.info("=" * 70)
        logger.info(f"  Agent running: {len(self.master_processes)} masters → {len(self.client_processes)} clients")
        logger.info("  Copy rules:")
        logger.info("    low/medium/high/pro/expert → EXACT 1:1 copy")
        logger.info("    expert_pro → PROPORTIONAL (balance ratio × risk_multiplier)")
        logger.info("=" * 70)

    def _spawn_master_listener(self, master_id: str, master: MasterInfo):
        """Spawn a subprocess to monitor a master account."""
        if master_id in self.master_processes:
            proc = self.master_processes[master_id]
            if proc.is_alive():
                return  # Already running

        proc = multiprocessing.Process(
            target=master_listener_process,
            args=(master_id, master.login, master.password, master.server),
            name=f"Master-{master.login}",
            daemon=True,
        )
        proc.start()
        self.master_processes[master_id] = proc
        logger.info(f"Spawned master listener: login={master.login} pid={proc.pid}")

    def _spawn_executor(self, client_id: str, client: ClientInfo):
        """Spawn a subprocess to execute trades on a client account."""
        if client_id in self.client_processes:
            proc = self.client_processes[client_id]
            if proc.is_alive():
                return

        proc = multiprocessing.Process(
            target=executor_process,
            args=(client_id, client.login, client.password, client.server),
            name=f"Exec-{client.login}",
            daemon=True,
        )
        proc.start()
        self.client_processes[client_id] = proc
        logger.info(f"Spawned executor: login={client.login} pid={proc.pid}")

    def _stop_master_listener(self, master_id: str):
        proc = self.master_processes.pop(master_id, None)
        if proc and proc.is_alive():
            proc.terminate()
            proc.join(timeout=5)
            logger.info(f"Stopped master listener: {master_id}")

    def _stop_executor(self, client_id: str):
        proc = self.client_processes.pop(client_id, None)
        if proc and proc.is_alive():
            proc.terminate()
            proc.join(timeout=5)
            logger.info(f"Stopped executor: {client_id}")

    def _on_masters_changed(self, added: Dict[str, MasterInfo], removed: Set[str],
                             all_masters: Dict[str, MasterInfo]):
        """Called by DBSynchronizer when master accounts change."""
        for master_id in removed:
            self._stop_master_listener(master_id)

        for master_id, master in added.items():
            self._spawn_master_listener(master_id, master)

        # Invalidate distributor cache
        if self.distributor:
            self.distributor.client_cache.invalidate()

    def _on_clients_changed(self, added: Dict[str, ClientInfo], removed: Set[str],
                             all_clients: Dict[str, ClientInfo]):
        """Called by DBSynchronizer when client accounts change."""
        for client_id in removed:
            self._stop_executor(client_id)

        for client_id, client in added.items():
            self._spawn_executor(client_id, client)

    def _check_processes(self):
        """Check for crashed processes and restart them."""
        # Masters
        for master_id, proc in list(self.master_processes.items()):
            if not proc.is_alive():
                logger.warning(f"Master {master_id} process died (exit={proc.exitcode}), restarting...")
                master = self.db_sync.masters.get(master_id)
                if master:
                    self._spawn_master_listener(master_id, master)

        # Clients
        for client_id, proc in list(self.client_processes.items()):
            if not proc.is_alive():
                logger.warning(f"Client {client_id} process died (exit={proc.exitcode}), restarting...")
                client = self.db_sync.clients.get(client_id)
                if client:
                    self._spawn_executor(client_id, client)

    def stop(self):
        logger.info("Shutting down Copy Agent...")
        self._running = False

        # Stop DB sync
        if self.db_sync:
            self.db_sync.stop()

        # Stop distributor
        if self.distributor:
            self.distributor.stop()

        # Stop result tracker
        if self.result_tracker:
            self.result_tracker.stop()

        # Stop all master listeners
        for master_id in list(self.master_processes.keys()):
            self._stop_master_listener(master_id)

        # Stop all executors
        for client_id in list(self.client_processes.keys()):
            self._stop_executor(client_id)

        logger.info("Copy Agent stopped.")

    def run_forever(self):
        """Main loop — keep agent alive and monitor processes."""
        try:
            while self._running:
                time.sleep(15)

                # Health check — restart crashed processes
                self._check_processes()

                # Log status
                alive_masters = sum(1 for p in self.master_processes.values() if p.is_alive())
                alive_clients = sum(1 for p in self.client_processes.values() if p.is_alive())
                logger.info(
                    f"Agent status: {alive_masters}/{len(self.master_processes)} masters, "
                    f"{alive_clients}/{len(self.client_processes)} clients"
                )

        except KeyboardInterrupt:
            self.stop()


def main():
    agent = CopyAgent()

    def shutdown(signum, frame):
        agent.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    agent.start()
    agent.run_forever()


if __name__ == "__main__":
    main()
