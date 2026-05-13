"""V2 Agent Bootstrapper.

Loads configuration from DB and wires all components:
  1. TerminalAllocator (loads strategy pools)
  2. PoolWorkerRegistry (per-pool executors)
  3. MasterMonitor (per master)
  4. Distributor (Redis events → Worker Registry)
  5. MasterSync (Balance/Equity)
  6. HealthMonitor

Safety defaults:
  V2_EXECUTION_MODE=DRY_RUN
  V2_ORDER_EXECUTION_ENABLED=false
"""

from __future__ import annotations

import signal
import threading
import time
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import text

from .config import get_v2_settings
from .db import session_scope
from .distributor import DistributorV2, ClientAccount
from .pool.health_monitor import HealthMonitor
from .pool.institutional_heartbeat_service import InstitutionalHeartbeatService
from .pool.state_recovery_service import StateRecoveryService
from .master_monitor import MasterMonitor
from .pool.allocator import TerminalAllocator
from .pool.repo import get_account_details, get_account_mapping, insert_account_mapping
from .utils.logger import get_logger
from .wiring import PoolWorkerRegistry


class MasterSync(threading.Thread):
    """Periodically syncs master balance/equity to DB."""

    def __init__(self, masters: List[dict]):
        super().__init__(name="v2-master-sync", daemon=True)
        self.masters = masters
        self.settings = get_v2_settings()
        self._stop = threading.Event()
        self.log = get_logger("master_sync")

    def stop(self):
        self._stop.set()

    def run(self):
        self.log.info("master sync thread started")
        while not self._stop.is_set():
            try:
                self._sync_all()
            except Exception as e:
                self.log.error("sync_all failed", exc_info=e)
            self._stop.wait(self.settings.BALANCE_SYNC_INTERVAL_S)

    def _sync_all(self):
        import MetaTrader5 as mt5 # type: ignore
        for m in self.masters:
            if self._stop.is_set(): break
            # Logic: initialize/login to master terminal and get info
            # For now, we assume MasterMonitor might have shared connection or we do it here.
            # Real implementation would update `master_accounts` table.
            pass


class V2Bootstrap:
    def __init__(self):
        self.settings = get_v2_settings()
        self.log = get_logger("bootstrap")
        self.registry = PoolWorkerRegistry()
        self.allocator: Optional[TerminalAllocator] = None
        self.distributor: Optional[DistributorV2] = None
        self.monitors: List[MasterMonitor] = []
        self.master_sync: Optional[MasterSync] = None
        self.health: Optional[HealthMonitor] = None
        self.heartbeat: Optional[InstitutionalHeartbeatService] = None
        self.recovery: Optional[StateRecoveryService] = None
        self.stop_event = threading.Event()

    def _load_v2_masters(self) -> List[dict]:
        with session_scope() as s:
            rows = s.execute(text(
                "SELECT m.id, m.login, m.terminal_path, m.strategy_id, s.name as strategy_name "
                "FROM master_accounts m "
                "JOIN v2_master_flags f ON m.id = f.master_id "
                "JOIN strategies s ON m.strategy_id = s.id "
                "WHERE f.enabled = true"
            )).fetchall()
            return [dict(r._mapping) for r in rows]

    def _client_resolver(self, master_id: UUID, strategy_id: UUID) -> List[ClientAccount]:
        """Resolves clients flagged for V2 that should copy this strategy."""
        with session_scope() as s:
            rows = s.execute(text(
                "SELECT a.id, a.login, a.account_type, f.state, a.balance, a.executor_version "
                "FROM mt5_accounts a "
                "JOIN v2_account_flags f ON a.id = f.account_id "
                "WHERE a.strategy_id = :sid AND f.enabled = true "
                "AND a.executor_version = :ver"
            ), {"sid": str(strategy_id), "ver": self.settings.V2_ROUTING_VERSION}).fetchall()
            
            return [
                ClientAccount(
                    account_id=r.id,
                    login=int(r.login),
                    account_type=r.account_type,
                    state=r.state,
                    balance=float(r.balance or 0.0)
                )
                for r in rows
            ]

    def _strategy_key_resolver(self, strategy_id: UUID) -> str:
        with session_scope() as s:
            name = s.execute(text("SELECT name FROM strategies WHERE id = :sid"), 
                            {"sid": str(strategy_id)}).scalar()
            return str(name or "unknown").lower()

    def start(self):
        self.log.info("V2 Bootstrap starting", extra={"mode": self.settings.EXECUTION_MODE})
        
        # 1. Load masters
        masters = self._load_v2_masters()
        if not masters:
            self.log.warning("no V2 masters found enabled; idling")

        # 2. Allocator
        self.allocator = TerminalAllocator(strategy_key_resolver=self._strategy_key_resolver)

        # 3. Distributor
        self.distributor = DistributorV2(
            allocator=self.allocator,
            worker_registry=self.registry,
            client_resolver=self._client_resolver
        )
        self.distributor.start()

        # 4. Master Monitors
        for m in masters:
            mon = MasterMonitor(
                master_id=m["id"],
                strategy_id=m["strategy_id"],
                terminal_path=m["terminal_path"],
                login=m["login"]
            )
            mon.start()
            self.monitors.append(mon)

        # 5. Registry wiring (lazy worker building)
        # We need to bridge registry with repo
        original_get_or_create = self.registry.get_or_create
        def _patched_get_or_create(pool):
            return original_get_or_create(
                pool,
                account_login_resolver=lambda aid: get_account_details(aid).login,
                account_details_loader=get_account_details,
                account_type_resolver=lambda aid: get_account_details(aid).account_type
            )
        self.registry.get_or_create = _patched_get_or_create

        # 6. Master Sync
        self.master_sync = MasterSync(masters)
        self.master_sync.start()

        # 7. Health & Institutional Monitoring
        def _get_terminals():
            return [w.pool for w in self.registry.all()]
        def _get_sessions(tid):
            w = self.registry.get(tid)
            return [w.session] if w else []

        self.health = HealthMonitor(
            get_terminals=_get_terminals,
            get_sessions=_get_sessions
        )
        self.health.start()

        # 8. Institutional Heartbeat
        self.heartbeat = InstitutionalHeartbeatService(
            vps_id=self.settings.V2_VPS_ID,
            get_stats=self.health.get_global_metrics
        )
        self.heartbeat.start()

        # 9. Recovery (optional after boot)
        if self.settings.V2_AUTO_RECOVERY_AFTER_REBOOT:
            self.recovery = StateRecoveryService(self.allocator, self.registry)
            self.recovery.recover()


        self.log.info("V2 Bootstrap complete")

    def stop(self):
        self.log.info("V2 Bootstrap stopping")
        if self.heartbeat: self.heartbeat.stop()
        if self.health: self.health.stop()
        if self.master_sync: self.master_sync.stop()
        for mon in self.monitors: mon.stop()
        if self.distributor: self.distributor.stop()
        self.registry.stop_all()
        self.log.info("V2 Bootstrap stopped")


def run():
    boot = V2Bootstrap()
    boot.start()

    def _handler(signum, frame):
        boot.stop_event.set()

    signal.signal(signal.SIGINT, _handler)
    signal.signal(signal.SIGTERM, _handler)

    while not boot.stop_event.is_set():
        time.sleep(1.0)
    
    boot.stop()

if __name__ == "__main__":
    run()
