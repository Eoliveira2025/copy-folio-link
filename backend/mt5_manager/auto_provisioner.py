"""
Auto Provisioner — polls the database for newly connected MT5 accounts
and automatically spawns terminal processes for them.

Also listens for Redis events from the API (new connections, disconnections).
"""

from __future__ import annotations
import time
import json
import logging
import threading
import redis
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from mt5_manager.config import get_manager_settings
from mt5_manager.terminal_pool import TerminalPool
from mt5_manager.credential_vault import decrypt_password

settings = get_manager_settings()
logger = logging.getLogger("mt5_manager.provisioner")


class AutoProvisioner(threading.Thread):
    """
    Two provisioning modes:
      1. Event-driven: listens to Redis channel 'mt5mgr:provision' for real-time events
      2. Polling: periodically scans DB for accounts not yet in the pool (catch-up)
    """

    def __init__(self, pool: TerminalPool):
        super().__init__(daemon=True, name="AutoProvisioner")
        self.pool = pool
        self.running = False
        self.redis_client = redis.from_url(settings.REDIS_URL)
        self.db_engine = create_engine(settings.DATABASE_URL_SYNC)
        self._last_poll = 0.0

    def _load_all_accounts(self) -> list[dict]:
        """Load all MT5 accounts that should be connected."""
        with Session(self.db_engine) as db:
            rows = db.execute(text("""
                SELECT
                    ma.id AS account_id,
                    ma.login,
                    ma.encrypted_password,
                    ma.server,
                    'client' AS role
                FROM mt5_accounts ma
                WHERE ma.status = 'connected'

                UNION ALL

                SELECT
                    master.id AS account_id,
                    master.login,
                    '' AS encrypted_password,
                    master.server,
                    'master' AS role
                FROM master_accounts master
            """)).fetchall()

            return [
                {
                    "account_id": str(r.account_id),
                    "login": r.login,
                    "encrypted_password": r.encrypted_password,
                    "server": r.server,
                    "role": r.role,
                }
                for r in rows
            ]

    def _provision_missing(self):
        """Scan DB and spawn terminals for accounts not in the pool."""
        accounts = self._load_all_accounts()
        spawned = 0

        for acct in accounts:
            if acct["account_id"] in self.pool.terminals:
                continue  # Already managed

            try:
                if acct["role"] == "client":
                    password = decrypt_password(acct["encrypted_password"])
                else:
                    # Master account passwords from secure vault / env
                    password = self._get_master_password(acct["login"])

                success = self.pool.spawn_terminal(
                    account_id=acct["account_id"],
                    login=acct["login"],
                    password=password,
                    server=acct["server"],
                    role=acct["role"],
                )
                if success:
                    spawned += 1

            except Exception as e:
                logger.error(f"Failed to provision login={acct['login']}: {e}")

        if spawned:
            logger.info(f"Provisioned {spawned} new terminals")

    def _get_master_password(self, login: int) -> str:
        """
        Retrieve master account password from secure storage.
        In production, use a KMS (AWS Secrets Manager, HashiCorp Vault, etc.)
        """
        # TODO: implement KMS integration
        # For now, master passwords can be stored as environment variables
        import os
        return os.environ.get(f"MASTER_PASSWORD_{login}", "")

    def _handle_provision_event(self, event: dict):
        """Handle a real-time provision/deprovision event from the API."""
        action = event.get("action")
        account_id = event.get("account_id")

        if action == "connect":
            login = event["login"]
            password = decrypt_password(event["encrypted_password"])
            server = event["server"]
            self.pool.spawn_terminal(account_id, login, password, server, role="client")
            logger.info(f"Provisioned on event: login={login}")

        elif action == "disconnect":
            self.pool.stop_terminal(account_id)
            logger.info(f"De-provisioned on event: account={account_id}")

        elif action == "reconnect":
            password = decrypt_password(event["encrypted_password"])
            self.pool.restart_terminal(account_id, password)
            logger.info(f"Reconnected on event: account={account_id}")

    def run(self):
        self.running = True
        pubsub = self.redis_client.pubsub()
        pubsub.subscribe("mt5mgr:provision")

        logger.info("Auto Provisioner started")

        # Initial provisioning
        self._provision_missing()

        while self.running:
            try:
                # Check for real-time events (non-blocking)
                message = pubsub.get_message(timeout=1.0)
                if message and message["type"] == "message":
                    event = json.loads(message["data"])
                    self._handle_provision_event(event)

                # Periodic catch-up poll
                now = time.time()
                if now - self._last_poll > settings.PROVISION_POLL_INTERVAL_S:
                    self._provision_missing()
                    self._last_poll = now

            except Exception as e:
                logger.error(f"Provisioner error: {e}", exc_info=True)
                time.sleep(5)

    def stop(self):
        self.running = False
