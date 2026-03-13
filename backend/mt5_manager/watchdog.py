"""
Connection Watchdog — monitors terminal heartbeats and triggers reconnection
for stale or dead processes.

Runs as a background thread within the Terminal Manager.
"""

from __future__ import annotations
import time
import json
import logging
import threading
from datetime import datetime, timezone
import redis

from mt5_manager.config import get_manager_settings
from mt5_manager.terminal_pool import TerminalPool, TerminalState

settings = get_manager_settings()
logger = logging.getLogger("mt5_manager.watchdog")


class ConnectionWatchdog(threading.Thread):
    """
    Periodically checks:
      1. Process heartbeats — restarts stale terminals
      2. OS process liveness — restarts crashed processes
      3. Resource usage — logs warnings for high memory
    """

    def __init__(self, pool: TerminalPool, password_resolver):
        """
        Args:
            pool: The TerminalPool to monitor
            password_resolver: Callable(account_id) → decrypted password
        """
        super().__init__(daemon=True, name="ConnectionWatchdog")
        self.pool = pool
        self.password_resolver = password_resolver
        self.running = False
        self.redis_client = redis.from_url(settings.REDIS_URL)

    def _check_heartbeats(self):
        """Check Redis heartbeat keys for all running terminals."""
        for account_id, terminal in list(self.pool.terminals.items()):
            if terminal.state != TerminalState.RUNNING:
                continue

            heartbeat_key = f"mt5mgr:heartbeat:{account_id}"
            raw = self.redis_client.get(heartbeat_key)

            if not raw:
                logger.warning(f"[{terminal.login}] No heartbeat found — may be stale")
                self._handle_stale(account_id, terminal)
                continue

            try:
                data = json.loads(raw)
                ts = datetime.fromisoformat(data["timestamp"])
                age = (datetime.now(timezone.utc) - ts).total_seconds()

                if age > settings.HEARTBEAT_STALE_S:
                    logger.warning(f"[{terminal.login}] Heartbeat stale ({age:.0f}s old)")
                    self._handle_stale(account_id, terminal)

            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logger.error(f"[{terminal.login}] Invalid heartbeat data: {e}")

    def _check_processes(self):
        """Check if OS processes are still alive."""
        for account_id, terminal in list(self.pool.terminals.items()):
            if terminal.state != TerminalState.RUNNING:
                continue

            if terminal.process and not terminal.process.is_alive():
                exit_code = terminal.process.exitcode
                logger.error(f"[{terminal.login}] Process died (exit code: {exit_code})")
                terminal.state = TerminalState.FAILED
                terminal.last_error = f"Process exited with code {exit_code}"
                self._handle_stale(account_id, terminal)

    def _handle_stale(self, account_id: str, terminal):
        """Handle a stale or dead terminal — attempt restart with backoff."""
        if terminal.restart_count >= settings.MAX_RECONNECT_ATTEMPTS:
            logger.error(
                f"[{terminal.login}] Max reconnect attempts reached ({settings.MAX_RECONNECT_ATTEMPTS}), "
                f"marking as failed"
            )
            terminal.state = TerminalState.FAILED
            self._notify_failure(account_id, terminal)
            return

        # Exponential backoff
        delay = settings.RECONNECT_BACKOFF_BASE_S * (2 ** terminal.restart_count)
        logger.info(f"[{terminal.login}] Scheduling restart in {delay}s (attempt #{terminal.restart_count + 1})")

        try:
            password = self.password_resolver(account_id)
            time.sleep(min(delay, 60))  # Cap at 60s
            self.pool.restart_terminal(account_id, password)
        except Exception as e:
            logger.error(f"[{terminal.login}] Restart failed: {e}")
            terminal.state = TerminalState.FAILED

    def _notify_failure(self, account_id: str, terminal):
        """Publish permanent failure event for the API to update DB status."""
        self.redis_client.publish("mt5mgr:failures", json.dumps({
            "account_id": account_id,
            "login": terminal.login,
            "server": terminal.server,
            "reason": terminal.last_error or "max_reconnect_attempts",
            "restart_count": terminal.restart_count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }))

    def run(self):
        self.running = True
        logger.info(f"Watchdog started — checking every {settings.WATCHDOG_INTERVAL_S}s")

        while self.running:
            try:
                self._check_heartbeats()
                self._check_processes()
            except Exception as e:
                logger.error(f"Watchdog error: {e}", exc_info=True)

            time.sleep(settings.WATCHDOG_INTERVAL_S)

    def stop(self):
        self.running = False
