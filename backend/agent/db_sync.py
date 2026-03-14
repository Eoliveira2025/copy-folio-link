"""
Database Synchronizer — periodically refreshes master and client account
lists from the remote PostgreSQL database.

Detects:
  - New master accounts → spawns new MasterListener
  - Removed master accounts → stops listener
  - New client accounts → spawns new ExecutionWorker
  - Removed client accounts → stops worker
  - Strategy changes → invalidates distributor cache
  - Balance updates → writes back to DB
"""

from __future__ import annotations
import logging
import time
import threading
from datetime import datetime, timezone
from typing import Dict, Set
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from cryptography.fernet import Fernet

from agent.config import get_agent_settings

settings = get_agent_settings()
logger = logging.getLogger("agent.db_sync")

_fernet = Fernet(settings.MT5_CREDENTIAL_KEY.encode())


def decrypt(encrypted: str) -> str:
    return _fernet.decrypt(encrypted.encode()).decode()


class MasterInfo:
    __slots__ = ("id", "login", "password", "server", "balance", "strategy_level")

    def __init__(self, id: str, login: int, password: str, server: str,
                 balance: float = 0.0, strategy_level: str = ""):
        self.id = id
        self.login = login
        self.password = password
        self.server = server
        self.balance = balance
        self.strategy_level = strategy_level


class ClientInfo:
    __slots__ = ("id", "login", "password", "server", "user_id", "strategy_level")

    def __init__(self, id: str, login: int, password: str, server: str,
                 user_id: str = "", strategy_level: str = "medium"):
        self.id = id
        self.login = login
        self.password = password
        self.server = server
        self.user_id = user_id
        self.strategy_level = strategy_level


class DBSynchronizer(threading.Thread):
    """Periodically syncs master and client account lists from PostgreSQL."""

    def __init__(self, on_masters_changed=None, on_clients_changed=None):
        super().__init__(daemon=True, name="DBSync")
        self.running = False
        self.db_engine = create_engine(
            settings.DATABASE_URL_SYNC,
            pool_size=5,
            pool_pre_ping=True,
        )
        self._on_masters_changed = on_masters_changed
        self._on_clients_changed = on_clients_changed

        self.masters: Dict[str, MasterInfo] = {}    # master_account_id → info
        self.clients: Dict[str, ClientInfo] = {}    # mt5_account_id → info
        self._known_master_ids: Set[str] = set()
        self._known_client_ids: Set[str] = set()

    def load_masters(self) -> Dict[str, MasterInfo]:
        """Load all active master accounts with decrypted passwords."""
        with Session(self.db_engine) as db:
            rows = db.execute(text("""
                SELECT
                    ma.id, ma.login, ma.encrypted_password, ma.server,
                    ma.balance, s.level AS strategy_level
                FROM master_accounts ma
                JOIN strategies s ON s.id = ma.strategy_id
                WHERE s.enabled = true
            """)).fetchall()

            result = {}
            for r in rows:
                try:
                    pwd = decrypt(r.encrypted_password) if r.encrypted_password else ""
                except Exception as e:
                    logger.error(f"Cannot decrypt master {r.login}: {e}")
                    continue

                result[str(r.id)] = MasterInfo(
                    id=str(r.id),
                    login=r.login,
                    password=pwd,
                    server=r.server,
                    balance=r.balance or 0.0,
                    strategy_level=r.strategy_level,
                )
            return result

    def load_clients(self) -> Dict[str, ClientInfo]:
        """Load all connected client MT5 accounts with decrypted passwords."""
        with Session(self.db_engine) as db:
            rows = db.execute(text("""
                SELECT
                    ma.id, ma.login, ma.encrypted_password, ma.server, ma.user_id
                FROM mt5_accounts ma
                WHERE ma.status = 'connected'
            """)).fetchall()

            result = {}
            for r in rows:
                try:
                    pwd = decrypt(r.encrypted_password)
                except Exception as e:
                    logger.error(f"Cannot decrypt client {r.login}: {e}")
                    continue

                result[str(r.id)] = ClientInfo(
                    id=str(r.id),
                    login=r.login,
                    password=pwd,
                    server=r.server,
                    user_id=str(r.user_id),
                )
            return result

    def sync_balance(self, account_id: str, balance: float, equity: float):
        """Write balance/equity back to the remote database."""
        try:
            with Session(self.db_engine) as db:
                db.execute(text("""
                    UPDATE mt5_accounts
                    SET balance = :balance, equity = :equity, last_connected_at = :now
                    WHERE id = :id
                """), {
                    "balance": balance,
                    "equity": equity,
                    "now": datetime.now(timezone.utc),
                    "id": account_id,
                })
                db.commit()
        except Exception as e:
            logger.error(f"Balance sync error for {account_id}: {e}")

    def sync_master_balance(self, master_id: str, balance: float):
        """Write master account balance back to the remote database."""
        try:
            with Session(self.db_engine) as db:
                db.execute(text("""
                    UPDATE master_accounts SET balance = :balance WHERE id = :id
                """), {"balance": balance, "id": master_id})
                db.commit()
        except Exception as e:
            logger.error(f"Master balance sync error for {master_id}: {e}")

    def _sync_cycle(self):
        """One synchronization cycle — detect changes and invoke callbacks."""
        # ── Masters ──
        new_masters = self.load_masters()
        new_ids = set(new_masters.keys())
        old_ids = self._known_master_ids

        added_masters = new_ids - old_ids
        removed_masters = old_ids - new_ids

        if added_masters or removed_masters:
            self.masters = new_masters
            self._known_master_ids = new_ids
            if self._on_masters_changed:
                self._on_masters_changed(
                    added={mid: new_masters[mid] for mid in added_masters},
                    removed=removed_masters,
                    all_masters=new_masters,
                )
            if added_masters:
                logger.info(f"New masters detected: {[new_masters[m].login for m in added_masters]}")
            if removed_masters:
                logger.info(f"Masters removed: {removed_masters}")
        else:
            self.masters = new_masters

        # ── Clients ──
        new_clients = self.load_clients()
        new_cids = set(new_clients.keys())
        old_cids = self._known_client_ids

        added_clients = new_cids - old_cids
        removed_clients = old_cids - new_cids

        if added_clients or removed_clients:
            self.clients = new_clients
            self._known_client_ids = new_cids
            if self._on_clients_changed:
                self._on_clients_changed(
                    added={cid: new_clients[cid] for cid in added_clients},
                    removed=removed_clients,
                    all_clients=new_clients,
                )
            if added_clients:
                logger.info(f"New clients detected: {[new_clients[c].login for c in added_clients]}")
            if removed_clients:
                logger.info(f"Clients removed: {removed_clients}")
        else:
            self.clients = new_clients

    def run(self):
        self.running = True
        logger.info(f"DB Synchronizer started (interval: {settings.DB_SYNC_INTERVAL_S}s)")

        # Initial load
        self._sync_cycle()

        while self.running:
            time.sleep(settings.DB_SYNC_INTERVAL_S)
            try:
                self._sync_cycle()
            except Exception as e:
                logger.error(f"DB sync error: {e}", exc_info=True)

    def stop(self):
        self.running = False
