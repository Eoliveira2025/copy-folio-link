"""
Terminal Process — the subprocess entry point for a POOLED MT5 terminal.

Each process manages MULTIPLE MT5 account sessions:
  1. Receives commands via Redis queue (mt5pool:cmd:{terminal_id})
  2. Maintains multiple MT5 connections using separate data directories
  3. Sends heartbeats per-account to Redis
  4. Routes trade commands to the correct account context

Note: MetaTrader5 Python API only supports ONE connection per process.
For multi-account, this process cycles through accounts or uses Wine with
separate terminal instances via subprocess. The implementation below uses
a sequential login approach where accounts share a terminal process and
the process manages connections by re-initializing MT5 with different
portable data directories.

Production alternative: Use Wine + portable MT5 terminals per data dir.
"""

from __future__ import annotations
import time
import json
import logging
import signal
import sys
import os
import subprocess
from datetime import datetime, timezone
from typing import Dict, Optional
from dataclasses import dataclass, field
import threading
import redis

from mt5_manager.config import get_manager_settings

settings = get_manager_settings()
logger = logging.getLogger("mt5_manager.terminal_process")


@dataclass
class AccountContext:
    """State for a single MT5 account within this terminal process."""
    account_id: str
    login: int
    password: str
    server: str
    role: str  # "master" or "client"
    connected: bool = False
    last_heartbeat: float = 0.0
    balance: float = 0.0
    equity: float = 0.0
    error: Optional[str] = None
    data_dir: Optional[str] = None  # Portable terminal data directory
    wine_pid: Optional[int] = None  # PID of Wine MT5 subprocess


class PooledTerminalProcess:
    """
    Manages multiple MT5 account sessions within a single terminal process.

    Uses portable MT5 terminal instances (each account gets its own data directory)
    running under Wine on Linux, or native on Windows.

    Architecture:
      ┌────────────────────────────────────────────────────┐
      │              Pooled Terminal Process                 │
      │                                                      │
      │  ┌──────────┐ ┌──────────┐ ┌──────────┐            │
      │  │ Account  │ │ Account  │ │ Account  │   ...      │
      │  │ ctx_001  │ │ ctx_002  │ │ ctx_003  │            │
      │  │ login=X  │ │ login=Y  │ │ login=Z  │            │
      │  └────┬─────┘ └────┬─────┘ └────┬─────┘            │
      │       │             │             │                  │
      │       ▼             ▼             ▼                  │
      │  ┌──────────────────────────────────────────┐       │
      │  │       MT5 API / Wine Subprocess Pool      │       │
      │  └──────────────────────────────────────────┘       │
      │                                                      │
      │  Redis cmd queue ◄── mt5pool:cmd:{terminal_id}      │
      │  Redis resp queue ──► mt5pool:resp:{terminal_id}    │
      └────────────────────────────────────────────────────┘
    """

    def __init__(self, terminal_id: str):
        self.terminal_id = terminal_id
        self.accounts: Dict[str, AccountContext] = {}
        self.running = False
        self.redis_client: Optional[redis.Redis] = None
        self._cmd_queue = f"mt5pool:cmd:{terminal_id}"
        self._resp_queue = f"mt5pool:resp:{terminal_id}"
        self._heartbeat_thread: Optional[threading.Thread] = None

    def _get_data_dir(self, account_id: str) -> str:
        """Get or create a portable data directory for an account."""
        data_dir = os.path.join(settings.MT5_DATA_DIR_BASE, f"account_{account_id}")
        os.makedirs(data_dir, exist_ok=True)
        return data_dir

    def _connect_account(self, ctx: AccountContext) -> bool:
        """Connect a single MT5 account using the MetaTrader5 API."""
        try:
            import MetaTrader5 as mt5

            ctx.data_dir = self._get_data_dir(ctx.account_id)

            # Initialize with portable path
            init_kwargs = {}
            if os.name == "nt":
                init_kwargs["path"] = settings.MT5_TERMINAL_PATH
            init_kwargs["portable"] = True

            if not mt5.initialize(**init_kwargs):
                error = mt5.last_error()
                ctx.error = f"MT5 init failed: {error}"
                logger.error(f"[{ctx.login}] {ctx.error}")
                return False

            authorized = mt5.login(ctx.login, password=ctx.password, server=ctx.server)
            if not authorized:
                error = mt5.last_error()
                ctx.error = f"Login failed: {error}"
                logger.error(f"[{ctx.login}] {ctx.error}")
                mt5.shutdown()
                return False

            info = mt5.account_info()
            if info:
                ctx.balance = info.balance
                ctx.equity = info.equity

            ctx.connected = True
            ctx.error = None
            logger.info(f"[{ctx.login}] Connected — Balance: {ctx.balance}, Equity: {ctx.equity}")
            mt5.shutdown()  # Release for next account
            return True

        except ImportError:
            # MT5 API not available (Linux without Wine) — use subprocess approach
            return self._connect_via_wine(ctx)
        except Exception as e:
            ctx.error = str(e)
            logger.error(f"[{ctx.login}] Connection error: {e}")
            return False

    def _connect_via_wine(self, ctx: AccountContext) -> bool:
        """
        Connect using Wine + headless MT5 terminal subprocess.
        Each account runs as a separate Wine process with its own data directory.
        """
        ctx.data_dir = self._get_data_dir(ctx.account_id)

        # Create account config file for MT5
        config_content = f"""[Common]
Login={ctx.login}
Password={ctx.password}
Server={ctx.server}
"""
        config_path = os.path.join(ctx.data_dir, "account.ini")
        with open(config_path, "w") as f:
            f.write(config_content)

        # Launch MT5 terminal via Wine (headless with Xvfb)
        try:
            wine_proc = subprocess.Popen(
                ["wine", settings.MT5_TERMINAL_PATH, f"/portable", f"/config:{config_path}"],
                cwd=ctx.data_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={**os.environ, "WINEPREFIX": os.path.join(ctx.data_dir, ".wine")},
            )
            ctx.wine_pid = wine_proc.pid
            ctx.connected = True
            ctx.error = None
            logger.info(f"[{ctx.login}] Wine MT5 started, pid={wine_proc.pid}")
            return True
        except Exception as e:
            ctx.error = f"Wine launch failed: {e}"
            logger.error(f"[{ctx.login}] {ctx.error}")
            return False

    def _disconnect_account(self, account_id: str):
        """Disconnect a single account."""
        ctx = self.accounts.get(account_id)
        if not ctx:
            return

        if ctx.wine_pid:
            try:
                os.kill(ctx.wine_pid, signal.SIGTERM)
            except (ProcessLookupError, OSError):
                pass
            ctx.wine_pid = None

        ctx.connected = False
        self._update_account_status(ctx, "disconnected")
        logger.info(f"[{ctx.login}] Disconnected")

    def _update_account_status(self, ctx: AccountContext, status: str):
        """Publish account status to Redis."""
        if not self.redis_client:
            return
        data = {
            "account_id": ctx.account_id,
            "terminal_id": self.terminal_id,
            "login": ctx.login,
            "server": ctx.server,
            "role": ctx.role,
            "status": status,
            "error": ctx.error,
            "balance": ctx.balance,
            "equity": ctx.equity,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.redis_client.set(f"mt5mgr:status:{ctx.account_id}", json.dumps(data), ex=120)

    def _send_heartbeats(self):
        """Background thread: send heartbeats for all connected accounts."""
        while self.running:
            for ctx in list(self.accounts.values()):
                if not ctx.connected:
                    continue
                try:
                    data = {
                        "account_id": ctx.account_id,
                        "terminal_id": self.terminal_id,
                        "login": ctx.login,
                        "role": ctx.role,
                        "connected": ctx.connected,
                        "balance": ctx.balance,
                        "equity": ctx.equity,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    self.redis_client.set(
                        f"mt5mgr:heartbeat:{ctx.account_id}",
                        json.dumps(data),
                        ex=settings.HEARTBEAT_STALE_S,
                    )
                except Exception:
                    pass
            time.sleep(settings.SESSION_HEARTBEAT_INTERVAL_S)

    def _handle_command(self, cmd: dict) -> dict:
        """Process a command received from the Terminal Pool."""
        action = cmd.get("action", "")
        request_id = cmd.get("request_id", "")
        account_id = cmd.get("account_id", "")

        response = {
            "request_id": request_id,
            "terminal_id": self.terminal_id,
            "action": action,
        }

        try:
            if action == "login":
                login = cmd["login"]
                password = cmd["password"]
                server = cmd["server"]
                role = cmd.get("role", "client")

                ctx = AccountContext(
                    account_id=account_id,
                    login=login,
                    password=password,
                    server=server,
                    role=role,
                )

                success = self._connect_account(ctx)
                if success:
                    self.accounts[account_id] = ctx
                    self._update_account_status(ctx, "connected")
                    response["status"] = "ok"
                    response["result"] = {"login": login, "balance": ctx.balance, "equity": ctx.equity}
                else:
                    response["status"] = "error"
                    response["error"] = ctx.error

            elif action == "disconnect":
                self._disconnect_account(account_id)
                self.accounts.pop(account_id, None)
                response["status"] = "ok"

            elif action == "account_info":
                ctx = self.accounts.get(account_id)
                if ctx:
                    response["result"] = {
                        "login": ctx.login,
                        "balance": ctx.balance,
                        "equity": ctx.equity,
                        "connected": ctx.connected,
                    }
                    response["status"] = "ok"
                else:
                    response["status"] = "error"
                    response["error"] = "Account not found"

            elif action == "ping":
                response["status"] = "ok"
                response["result"] = {
                    "accounts": len(self.accounts),
                    "connected": sum(1 for c in self.accounts.values() if c.connected),
                }

            elif action == "shutdown":
                for aid in list(self.accounts.keys()):
                    self._disconnect_account(aid)
                self.running = False
                response["status"] = "ok"

            elif action == "update_balance":
                ctx = self.accounts.get(account_id)
                if ctx and ctx.connected:
                    self.redis_client.publish("mt5mgr:balance_updates", json.dumps({
                        "account_id": account_id,
                        "balance": ctx.balance,
                        "equity": ctx.equity,
                    }))
                    response["status"] = "ok"
                else:
                    response["status"] = "error"

            else:
                response["status"] = "error"
                response["error"] = f"Unknown command: {action}"

        except Exception as e:
            response["status"] = "error"
            response["error"] = str(e)
            logger.error(f"[{self.terminal_id}] Command error ({action}): {e}", exc_info=True)

        return response

    def run(self):
        """Main loop: process commands from Redis, manage account sessions."""
        self.redis_client = redis.from_url(settings.REDIS_URL)
        self.running = True

        # Start heartbeat thread
        self._heartbeat_thread = threading.Thread(
            target=self._send_heartbeats, daemon=True, name=f"HB-{self.terminal_id}"
        )
        self._heartbeat_thread.start()

        logger.info(f"Pooled terminal {self.terminal_id} running, listening on {self._cmd_queue}")

        while self.running:
            try:
                result = self.redis_client.brpop(self._cmd_queue, timeout=2)
                if result:
                    _, raw = result
                    cmd = json.loads(raw)
                    response = self._handle_command(cmd)
                    self.redis_client.lpush(self._resp_queue, json.dumps(response))

            except redis.ConnectionError:
                logger.error(f"[{self.terminal_id}] Redis connection lost, retrying...")
                time.sleep(5)
                try:
                    self.redis_client = redis.from_url(settings.REDIS_URL)
                except Exception:
                    pass
            except Exception as e:
                logger.error(f"[{self.terminal_id}] Process error: {e}", exc_info=True)
                time.sleep(1)

        # Cleanup
        for account_id in list(self.accounts.keys()):
            self._disconnect_account(account_id)
        logger.info(f"Pooled terminal {self.terminal_id} exiting")


def subprocess_entry(terminal_id: str):
    """Entry point for multiprocessing.Process — pooled terminal."""
    logging.basicConfig(
        level=logging.INFO,
        format=f"%(asctime)s [Pool-{terminal_id}] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    proc = PooledTerminalProcess(terminal_id)

    def shutdown(signum, frame):
        proc.running = False

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    proc.run()
