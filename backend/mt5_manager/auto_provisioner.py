"""
Auto Provisioner — polls the database for newly connected MT5 accounts
and automatically provisions them into pooled terminals.

Works with:
  - TerminalPool (spawn/manage terminal processes)
  - TerminalAllocator (assign accounts to terminals)
  - SessionManager (track session lifecycle)
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
from mt5_manager.terminal_allocator import TerminalAllocator
from mt5_manager.account_session import SessionManager
from mt5_manager.credential_vault import decrypt_password

settings = get_manager_settings()
logger = logging.getLogger("mt5_manager.provisioner")


class AutoProvisioner(threading.Thread):
    """
    Two provisioning modes:
      1. Event-driven: listens to Redis channel 'mt5mgr:provision' for real-time events
      2. Polling: periodically scans DB for accounts not yet in the pool (catch-up)

    Also listens for 'mt5mgr:spawn_terminal' to auto-spawn new terminal processes.
    """

    def __init__(self, pool: TerminalPool, allocator: TerminalAllocator, session_manager: SessionManager):
        super().__init__(daemon=True, name="AutoProvisioner")
        self.pool = pool
        self.allocator = allocator
        self.session_manager = session_manager
        self.running = False
        self.redis_client = redis.from_url(settings.REDIS_URL)
        self.db_engine = create_engine(settings.DATABASE_URL_SYNC)
        self._last_poll = 0.0
        self._last_rebalance = 0.0

    def _load_all_accounts(self) -> list[dict]:
        """Load all MT5 accounts that should be connected."""
        with Session(self.db_engine) as db:
            rows = db.execute(text("""
                SELECT
                    ma.id AS account_id,
                    ma.user_id,
                    ma.login,
                    ma.encrypted_password,
                    ma.server,
                    ma.strategy_level,
                    'client' AS role
                FROM mt5_accounts ma
                WHERE ma.status = 'connected'
            """)).fetchall()

            return [
                {
                    "account_id": str(r.account_id),
                    "user_id": str(r.user_id),
                    "login": r.login,
                    "encrypted_password": r.encrypted_password,
                    "server": r.server,
                    "strategy_level": r.strategy_level or "medium",
                    "role": r.role,
                }
                for r in rows
            ]

    def _provision_account(self, acct: dict) -> bool:
        """Provision a single account: allocate terminal, create session, login."""
        account_id = acct["account_id"]
        strategy = acct.get("strategy_level", "medium")

        # 1. Allocate to a terminal
        terminal_id = self.allocator.allocate(account_id, strategy)
        if not terminal_id:
            # Try to spawn a new terminal
            new_id = self.pool.spawn_terminal()
            if new_id:
                self.allocator.register_terminal(new_id)
                terminal_id = self.allocator.allocate(account_id, strategy)

        if not terminal_id:
            logger.error(f"Cannot provision {acct['login']}: no terminal capacity")
            return False

        # 2. Create session
        session = self.session_manager.create_session(
            account_id=account_id,
            user_id=acct.get("user_id", ""),
            login=acct["login"],
            server=acct["server"],
            strategy_level=strategy,
        )

        # 3. Login to terminal
        try:
            password = decrypt_password(acct["encrypted_password"]) if acct.get("encrypted_password") else ""
            success = self.pool.add_account_to_terminal(
                terminal_id=terminal_id,
                account_id=account_id,
                login=acct["login"],
                password=password,
                server=acct["server"],
                role=acct["role"],
            )

            if success:
                self.session_manager.activate_session(account_id, terminal_id)
                logger.info(f"Provisioned: login={acct['login']} → terminal={terminal_id}")
                return True
            else:
                self.session_manager.mark_reconnecting(account_id, "Initial login failed")
                self.allocator.deallocate(account_id)
                return False

        except Exception as e:
            logger.error(f"Provision error for login={acct['login']}: {e}")
            self.session_manager.mark_failed(account_id, str(e))
            self.allocator.deallocate(account_id)
            return False

    def _provision_missing(self):
        """Scan DB and provision accounts not yet in session manager."""
        accounts = self._load_all_accounts()
        spawned = 0

        for acct in accounts:
            existing = self.session_manager.get_session(acct["account_id"])
            if existing and existing.state.value in ("active", "connecting", "reconnecting"):
                continue

            if self._provision_account(acct):
                spawned += 1

        if spawned:
            logger.info(f"Provisioned {spawned} new accounts")

    def _handle_provision_event(self, event: dict):
        """Handle a real-time provision/deprovision event from the API."""
        action = event.get("action")
        account_id = event.get("account_id")

        if action == "connect":
            acct = {
                "account_id": account_id,
                "user_id": event.get("user_id", ""),
                "login": event["login"],
                "encrypted_password": event.get("encrypted_password", ""),
                "server": event["server"],
                "strategy_level": event.get("strategy_level", "medium"),
                "role": "client",
            }
            self._provision_account(acct)

        elif action == "disconnect":
            self.pool.remove_account_from_terminal(account_id)
            self.allocator.deallocate(account_id)
            self.session_manager.disconnect_session(account_id)
            logger.info(f"De-provisioned: account={account_id}")

        elif action == "reconnect":
            # Re-provision the account
            terminal_id = event.get("terminal_id")
            session = self.session_manager.get_session(account_id)
            if session:
                self.session_manager.mark_reconnecting(account_id)
                # Will be picked up by next polling cycle
            logger.info(f"Reconnect requested: account={account_id}")

        elif action == "change_strategy":
            new_strategy = event.get("strategy_level", "medium")
            self.session_manager.change_strategy(account_id, new_strategy)

    def _handle_spawn_request(self, event: dict):
        """Handle a request to spawn a new terminal (from allocator overflow)."""
        terminal_id = event.get("terminal_id")
        if terminal_id and terminal_id not in self.pool.terminals:
            spawned_id = self.pool.spawn_terminal(terminal_id)
            if spawned_id:
                self.allocator.register_terminal(spawned_id)
                logger.info(f"Spawned new terminal on demand: {spawned_id}")

    def _maybe_rebalance(self):
        """Periodically rebalance accounts across terminals."""
        now = time.time()
        if now - self._last_rebalance < settings.REBALANCE_INTERVAL_S:
            return

        self._last_rebalance = now
        migrations = self.allocator.rebalance()

        for terminal_id, account_ids in migrations.items():
            for account_id in account_ids:
                # In production: migrate by disconnecting from old and reconnecting to new
                logger.info(f"Rebalance: would migrate {account_id} from {terminal_id}")

    def run(self):
        self.running = True
        pubsub = self.redis_client.pubsub()
        pubsub.subscribe("mt5mgr:provision", "mt5mgr:spawn_terminal")

        logger.info("Auto Provisioner started")

        # Initial provisioning
        self._provision_missing()

        while self.running:
            try:
                # Check for real-time events (non-blocking)
                message = pubsub.get_message(timeout=1.0)
                if message and message["type"] == "message":
                    event = json.loads(message["data"])
                    channel = message.get("channel", b"").decode() if isinstance(message.get("channel"), bytes) else message.get("channel", "")

                    if "spawn_terminal" in channel:
                        self._handle_spawn_request(event)
                    else:
                        self._handle_provision_event(event)

                # Periodic catch-up poll
                now = time.time()
                if now - self._last_poll > settings.PROVISION_POLL_INTERVAL_S:
                    self._provision_missing()
                    self._last_poll = now

                # Periodic rebalance
                self._maybe_rebalance()

            except Exception as e:
                logger.error(f"Provisioner error: {e}", exc_info=True)
                time.sleep(5)

    def stop(self):
        self.running = False
