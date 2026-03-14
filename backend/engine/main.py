"""
Copy Engine Orchestrator — ultra-low-latency edition.

Starts all engine components with optimized configurations:
  1. MasterListener per master (10ms polling)
  2. TradeDistributor (parallel fan-out with thread pool)
  3. ExecutionWorker per client (slippage control, retry with backoff)
  4. HealthMonitor (connection + queue monitoring)
  5. ResultTracker (latency-aware persistence)
  6. MetricsPublisher (Prometheus + Redis metrics)

Architecture:
  ┌─────────────────────────────────────────────────────────────────────┐
  │                 Copy Engine (Ultra-Low-Latency)                     │
  │                                                                     │
  │  ┌──────────────┐  10ms poll   ┌────────────────────┐              │
  │  │MasterListener├─────────────►│  TradeDistributor   │              │
  │  │ (per master) │  Redis pub   │  (thread pool ×16)  │              │
  │  └──────────────┘              └─────────┬──────────┘              │
  │                                          │ Redis pipeline           │
  │                     ┌────────────────────┼────────────────┐        │
  │                     ▼                    ▼                ▼        │
  │              ┌───────────┐        ┌───────────┐    ┌───────────┐  │
  │              │ Executor  │        │ Executor  │    │ Executor  │  │
  │              │ Worker 1  │        │ Worker 2  │    │ Worker N  │  │
  │              │ slippage  │        │ slippage  │    │ slippage  │  │
  │              │ + retry   │        │ + retry   │    │ + retry   │  │
  │              └─────┬─────┘        └─────┬─────┘    └─────┬─────┘  │
  │                    │                    │                │         │
  │                    └────────────────────┼────────────────┘         │
  │                                        ▼                           │
  │              ┌───────────────┐  ┌───────────────┐                  │
  │              │ResultTracker  │  │MetricsPublish │                  │
  │              │ (latency DB)  │  │ (Prometheus)  │                  │
  │              └───────────────┘  └───────────────┘                  │
  │                                                                     │
  │  Target: <100ms end-to-end (detect → execute)                      │
  │  Typical: ~30-50ms with local Redis                                │
  └─────────────────────────────────────────────────────────────────────┘
"""

import logging
import signal
import sys
import time
import os
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
from engine.metrics import get_metrics, MetricsPublisher

settings = get_engine_settings()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("engine.main")

_fernet = Fernet(settings.MT5_CREDENTIAL_KEY.encode())


def decrypt(encrypted: str) -> str:
    return _fernet.decrypt(encrypted.encode()).decode()


def load_master_accounts(db_engine) -> list[dict]:
    """Load all active master accounts with decrypted passwords."""
    with Session(db_engine) as db:
        rows = db.execute(text("""
            SELECT ma.id, ma.login, ma.server, ma.encrypted_password
            FROM master_accounts ma
            JOIN strategies s ON s.id = ma.strategy_id
            WHERE s.enabled = true
        """)).fetchall()
        return [
            {
                "id": str(r.id),
                "login": r.login,
                "server": r.server,
                "password": decrypt(r.encrypted_password),
            }
            for r in rows
        ]


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
    """Entry point for executor subprocess."""
    logging.basicConfig(
        level=logging.INFO,
        format=f"%(asctime)s.%(msecs)03d [Exec-{client['login']}] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    worker = ExecutionWorker(
        client_mt5_id=client["id"],
        login=client["login"],
        password=client["password"],
        server=client["server"],
    )
    worker.run()


def run_listener_subprocess(master: dict):
    """Entry point for master listener subprocess."""
    logging.basicConfig(
        level=logging.INFO,
        format=f"%(asctime)s.%(msecs)03d [Listen-{master['login']}] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    listener = MasterListener(
        master_account_id=master["id"],
        login=master["login"],
        password=master["password"],
        server=master["server"],
    )
    listener.run()


class CopyEngine:
    """Orchestrates all engine components with ultra-low-latency configuration."""

    def __init__(self):
        self.db_engine = create_engine(
            settings.DATABASE_URL_SYNC,
            pool_size=20,
            pool_pre_ping=True,
        )
        self.listener_processes: List[multiprocessing.Process] = []
        self.distributor: TradeDistributor | None = None
        self.health_monitor: HealthMonitor | None = None
        self.result_tracker: ResultTracker | None = None
        self.metrics_publisher: MetricsPublisher | None = None
        self.executor_processes: List[multiprocessing.Process] = []
        self._metrics = get_metrics()

    def start(self):
        logger.info("=" * 70)
        logger.info("  CopyTrade Pro — Ultra-Low-Latency Copy Engine")
        logger.info("=" * 70)
        logger.info(f"  Poll interval:     {settings.MASTER_POLL_INTERVAL_MS}ms")
        logger.info(f"  Max slippage:      {settings.MAX_SLIPPAGE_POINTS} points")
        logger.info(f"  Retry attempts:    {settings.MAX_RETRY_ATTEMPTS}")
        logger.info(f"  Retry backoff:     {settings.RETRY_BASE_DELAY_MS}ms (exponential)")
        logger.info(f"  Distributor pool:  {settings.DISTRIBUTOR_THREAD_POOL_SIZE} threads")
        logger.info(f"  Metrics port:      :{settings.METRICS_PORT}")
        logger.info("=" * 70)

        # 1. Metrics Publisher (start first for observability)
        self.metrics_publisher = MetricsPublisher(self._metrics)
        self.metrics_publisher.start()
        logger.info("✓ Metrics Publisher started (Prometheus on :%d)", settings.METRICS_PORT)

        # 2. Health Monitor
        self.health_monitor = HealthMonitor()
        self.health_monitor.start()
        logger.info("✓ Health Monitor started")

        # 3. Result Tracker
        self.result_tracker = ResultTracker()
        self.result_tracker.start()
        logger.info("✓ Result Tracker started")

        # 4. Trade Distributor
        self.distributor = TradeDistributor()
        self.distributor.start()
        logger.info("✓ Trade Distributor started")

        # 5. Master Listeners (each in a subprocess due to MT5 API limitation)
        masters = load_master_accounts(self.db_engine)
        for master in masters:
            proc = multiprocessing.Process(
                target=run_listener_subprocess,
                args=(master,),
                name=f"Listener-{master['login']}",
                daemon=True,
            )
            proc.start()
            self.listener_processes.append(proc)
        self._metrics.set_gauges(listeners=len(masters))
        logger.info(f"✓ {len(masters)} Master Listeners started (10ms polling)")

        # 6. Execution Workers (one subprocess per client)
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
        self._metrics.set_gauges(workers=len(clients))
        logger.info(f"✓ {len(clients)} Execution Workers started")

        logger.info("=" * 70)
        logger.info(f"  Engine running: {len(masters)} masters → {len(clients)} clients")
        logger.info(f"  Latency target: <100ms end-to-end")
        logger.info("=" * 70)

    def stop(self):
        logger.info("Shutting down Copy Engine...")

        for proc in self.listener_processes:
            proc.terminate()
            proc.join(timeout=3)

        if self.distributor:
            self.distributor.stop()

        for proc in self.executor_processes:
            proc.terminate()
            proc.join(timeout=3)

        if self.health_monitor:
            self.health_monitor.stop()
        if self.result_tracker:
            self.result_tracker.stop()
        if self.metrics_publisher:
            self.metrics_publisher.stop()

        # Print final metrics
        logger.info("=" * 70)
        logger.info("  Final Metrics:")
        metrics = self._metrics.to_dict()
        logger.info(f"  Events detected:    {metrics['counters']['events_detected']}")
        logger.info(f"  Orders executed:    {metrics['counters']['orders_executed']}")
        logger.info(f"  Orders failed:      {metrics['counters']['orders_failed']}")
        logger.info(f"  Success rate:       {metrics['counters']['success_rate_pct']}%")
        lat = metrics["latency"]["total_e2e"]
        logger.info(f"  Avg latency:        {lat['avg_ms']}ms")
        logger.info(f"  P95 latency:        {lat['p95_ms']}ms")
        logger.info(f"  P99 latency:        {lat['p99_ms']}ms")
        logger.info(f"  Avg slippage:       {metrics['slippage']['avg_points']} points")
        logger.info("=" * 70)

        logger.info("Copy Engine stopped.")


def main():
    engine = CopyEngine()

    def shutdown_handler(signum, frame):
        engine.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    engine.start()

    try:
        while True:
            time.sleep(10)
            metrics = engine._metrics.to_dict()
            lat = metrics["latency"]["total_e2e"]
            logger.info(
                f"Engine: {metrics['counters']['events_detected']} events | "
                f"{metrics['counters']['orders_executed']} exec | "
                f"{metrics['counters']['success_rate_pct']}% success | "
                f"avg={lat['avg_ms']}ms p99={lat['p99_ms']}ms | "
                f"slip={metrics['slippage']['avg_points']}pts"
            )
    except KeyboardInterrupt:
        engine.stop()


if __name__ == "__main__":
    main()
