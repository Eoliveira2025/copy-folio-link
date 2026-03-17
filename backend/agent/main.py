"""
CopyTrade Pro — Windows VPS Copy Agent
=======================================

Main entry point. Orchestrates all components:
  1. MT5InstanceManager — manages separate MT5 folders per account
  2. DBSynchronizer — polls PostgreSQL for account changes
  3. MasterMonitor — one subprocess per master account (dedicated MT5 instance)
  4. TradeDistributor — fans out trade events to client queues
  5. ExecutionWorker — one subprocess per client account (dedicated MT5 instance)
  6. ResultTracker — persists results to PostgreSQL

Usage:
  cd backend
  python -m agent.main

Requires:
  - Windows Server with Python 3.12 and MetaTrader 5 base installation
  - .env file with DATABASE_URL_SYNC, REDIS_URL, MT5_CREDENTIAL_KEY
  - MT5_BASE_PATH pointing to the base MT5 installation folder
  - MT5_INSTANCES_DIR for per-account instance copies
"""

import logging
import signal
import sys
import time
import multiprocessing
from typing import Dict, Set

from agent.config import get_agent_settings
from agent.instance_manager import MT5InstanceManager
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

    Each MT5 account (master or client) gets its own terminal installation
    folder via MT5InstanceManager to allow simultaneous connections.
    """

    def __init__(self):
        self.instance_manager = MT5InstanceManager()
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
        logger.info(f"  Database:       {settings.DATABASE_URL_SYNC.split('@')[1] if '@' in settings.DATABASE_URL_SYNC else 'local'}")
        logger.info(f"  Redis:          {settings.REDIS_URL.split('@')[1] if '@' in settings.REDIS_URL else settings.REDIS_URL}")
        logger.info(f"  MT5 Base:       {settings.MT5_BASE_PATH}")
        logger.info(f"  Instances Dir:  {settings.MT5_INSTANCES_DIR}")
        logger.info(f"  Poll interval:  {settings.MASTER_POLL_INTERVAL_MS}ms")
        logger.info(f"  Max slippage:   {settings.MAX_SLIPPAGE_POINTS} points")
        logger.info(f"  DB sync:        every {settings.DB_SYNC_INTERVAL_S}s")
        logger.info(f"  Init timeout:   {settings.MT5_INIT_TIMEOUT_MS}ms")
        logger.info("=" * 70)

        self._running = True

        # 1. DB Synchronizer
        self.db_sync = DBSynchronizer(
            on_masters_changed=self._on_masters_changed,
            on_clients_changed=self._on_clients_changed,
        )
        self.db_sync.start()
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

        # 4. Spawn master listeners (each with dedicated MT5 instance)
        for master_id, master in self.db_sync.masters.items():
            self._spawn_master_listener(master_id, master)
        logger.info(f"✓ {len(self.master_processes)} Master Listeners started")

        # 5. Spawn execution workers (each with dedicated MT5 instance)
        for client_id, client in self.db_sync.clients.items():
            self._spawn_executor(client_id, client)
        logger.info(f"✓ {len(self.client_processes)} Execution Workers started")

        # Log instance summary
        instances = self.instance_manager.get_all_instances()
        logger.info(f"✓ MT5 Instances: {len(instances)} folders in {settings.MT5_INSTANCES_DIR}")

        logger.info("=" * 70)
        logger.info(f"  Agent running: {len(self.master_processes)} masters → {len(self.client_processes)} clients")
        logger.info("  Copy rules:")
        logger.info("    low/medium/high/pro/expert → EXACT 1:1 copy")
        logger.info("    expert_pro → PROPORTIONAL (balance ratio × risk_multiplier)")
        logger.info("=" * 70)

    def _spawn_master_listener(self, master_id: str, master: MasterInfo):
        """Spawn a subprocess to monitor a master account with its own MT5 instance."""
        if master_id in self.master_processes:
            proc = self.master_processes[master_id]
            if proc.is_alive():
                return

        # Get dedicated terminal path for this master
        account_key = f"master_{master_id}"
        terminal_path = self.instance_manager.get_terminal_path(account_key)
        logger.info(f"Master {master.login} → instance: {terminal_path}")

        proc = multiprocessing.Process(
            target=master_listener_process,
            args=(master_id, master.login, master.password, master.server, terminal_path),
            name=f"Master-{master.login}",
            daemon=True,
        )
        proc.start()
        self.master_processes[master_id] = proc
        logger.info(f"Spawned master listener: login={master.login} pid={proc.pid}")

    def _spawn_executor(self, client_id: str, client: ClientInfo):
        """Spawn a subprocess to execute trades on a client account with its own MT5 instance."""
        if client_id in self.client_processes:
            proc = self.client_processes[client_id]
            if proc.is_alive():
                return

        # Get dedicated terminal path for this client
        account_key = f"client_{client_id}"
        terminal_path = self.instance_manager.get_terminal_path(account_key)
        logger.info(f"Client {client.login} → instance: {terminal_path}")

        proc = multiprocessing.Process(
            target=executor_process,
            args=(client_id, client.login, client.password, client.server, terminal_path),
            name=f"Exec-{client.login}",
            daemon=True,
        )
        proc.start()
        self.client_processes[client_id] = proc
        logger.info(f"Spawned executor: login={client.login} pid={proc.pid}")

    def _stop_master_listener(self, master_id: str, release_instance: bool = True):
        proc = self.master_processes.pop(master_id, None)
        if proc and proc.is_alive():
            proc.terminate()
            proc.join(timeout=5)
            logger.info(f"Stopped master listener: {master_id}")

        if release_instance:
            self.instance_manager.release_instance(f"master_{master_id}")

    def _stop_executor(self, client_id: str, release_instance: bool = True):
        proc = self.client_processes.pop(client_id, None)
        if proc and proc.is_alive():
            proc.terminate()
            proc.join(timeout=5)
            logger.info(f"Stopped executor: {client_id}")

        if release_instance:
            self.instance_manager.release_instance(f"client_{client_id}")

    def _on_masters_changed(self, added: Dict[str, MasterInfo], removed: Set[str],
                             all_masters: Dict[str, MasterInfo]):
        for master_id in removed:
            self._stop_master_listener(master_id, release_instance=True)

        for master_id, master in added.items():
            self._spawn_master_listener(master_id, master)

        if self.distributor:
            self.distributor.client_cache.invalidate()

    def _on_clients_changed(self, added: Dict[str, ClientInfo], removed: Set[str],
                             all_clients: Dict[str, ClientInfo]):
        for client_id in removed:
            self._stop_executor(client_id, release_instance=True)

        for client_id, client in added.items():
            self._spawn_executor(client_id, client)

    def _check_processes(self):
        """Check for crashed processes and restart them (reusing same instance folder)."""
        for master_id, proc in list(self.master_processes.items()):
            if not proc.is_alive():
                logger.warning(f"Master {master_id} process died (exit={proc.exitcode}), restarting...")
                # Remove dead process but keep instance folder
                self.master_processes.pop(master_id, None)
                master = self.db_sync.masters.get(master_id)
                if master:
                    self._spawn_master_listener(master_id, master)

        for client_id, proc in list(self.client_processes.items()):
            if not proc.is_alive():
                logger.warning(f"Client {client_id} process died (exit={proc.exitcode}), restarting...")
                self.client_processes.pop(client_id, None)
                client = self.db_sync.clients.get(client_id)
                if client:
                    self._spawn_executor(client_id, client)

    def stop(self):
        logger.info("Shutting down Copy Agent...")
        self._running = False

        if self.db_sync:
            self.db_sync.stop()
        if self.distributor:
            self.distributor.stop()
        if self.result_tracker:
            self.result_tracker.stop()

        # Stop all processes (but keep instance folders for restart)
        for master_id in list(self.master_processes.keys()):
            self._stop_master_listener(master_id, release_instance=False)

        for client_id in list(self.client_processes.keys()):
            self._stop_executor(client_id, release_instance=False)

        logger.info("Copy Agent stopped. Instance folders preserved for restart.")

    def run_forever(self):
        try:
            while self._running:
                time.sleep(15)
                self._check_processes()

                alive_masters = sum(1 for p in self.master_processes.values() if p.is_alive())
                alive_clients = sum(1 for p in self.client_processes.values() if p.is_alive())
                logger.info(
                    f"Agent status: {alive_masters}/{len(self.master_processes)} masters, "
                    f"{alive_clients}/{len(self.client_processes)} clients, "
                    f"{len(self.instance_manager.get_all_instances())} MT5 instances"
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
