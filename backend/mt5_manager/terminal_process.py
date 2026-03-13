"""
Terminal Process — the subprocess entry point for a single MT5 connection.

Each process:
  1. Initializes its own MT5 terminal instance
  2. Logs into the assigned account
  3. Listens for commands on a Redis queue
  4. Sends heartbeats to Redis
  5. Responds with account info, balance updates, and execution results
"""

from __future__ import annotations
import time
import json
import logging
import signal
import sys
from datetime import datetime, timezone
from typing import Optional
import redis
import MetaTrader5 as mt5

from mt5_manager.config import get_manager_settings

settings = get_manager_settings()
logger = logging.getLogger("mt5_manager.terminal_process")

# Redis key patterns
CMD_QUEUE = "mt5mgr:cmd:{account_id}"       # Commands TO this process
RESP_QUEUE = "mt5mgr:resp:{account_id}"      # Responses FROM this process
HEARTBEAT_KEY = "mt5mgr:heartbeat:{account_id}"
STATUS_KEY = "mt5mgr:status:{account_id}"


class TerminalProcess:
    """
    Runs inside a subprocess. Manages a single MT5 terminal connection
    and processes commands from the Terminal Pool via Redis.
    """

    def __init__(self, account_id: str, login: int, password: str, server: str, role: str = "client"):
        self.account_id = account_id
        self.login = login
        self.password = password
        self.server = server
        self.role = role  # "master" or "client"
        self.running = False
        self.connected = False
        self.redis_client: Optional[redis.Redis] = None
        self._cmd_queue = CMD_QUEUE.format(account_id=account_id)
        self._resp_queue = RESP_QUEUE.format(account_id=account_id)
        self._heartbeat_key = HEARTBEAT_KEY.format(account_id=account_id)
        self._status_key = STATUS_KEY.format(account_id=account_id)
        self._last_heartbeat = 0.0

    def _connect_mt5(self) -> bool:
        """Initialize MT5 and authenticate."""
        logger.info(f"[{self.login}] Initializing MT5 terminal...")

        if not mt5.initialize():
            error = mt5.last_error()
            logger.error(f"[{self.login}] MT5 initialize failed: {error}")
            self._update_status("error", f"Initialize failed: {error}")
            return False

        logger.info(f"[{self.login}] Logging in to {self.server}...")
        authorized = mt5.login(self.login, password=self.password, server=self.server)

        if not authorized:
            error = mt5.last_error()
            logger.error(f"[{self.login}] Login failed: {error}")
            self._update_status("error", f"Login failed: {error}")
            mt5.shutdown()
            return False

        account_info = mt5.account_info()
        if account_info:
            logger.info(
                f"[{self.login}] Connected — Balance: {account_info.balance}, "
                f"Equity: {account_info.equity}, Server: {account_info.server}"
            )

        self.connected = True
        self._update_status("connected")
        return True

    def _disconnect_mt5(self):
        """Shutdown MT5 terminal."""
        try:
            mt5.shutdown()
        except Exception:
            pass
        self.connected = False
        self._update_status("disconnected")
        logger.info(f"[{self.login}] Disconnected")

    def _update_status(self, status: str, error: str | None = None):
        """Publish current status to Redis."""
        if not self.redis_client:
            return
        data = {
            "account_id": self.account_id,
            "login": self.login,
            "server": self.server,
            "role": self.role,
            "status": status,
            "error": error,
            "pid": sys.modules.get("os", __import__("os")).getpid(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.redis_client.set(self._status_key, json.dumps(data), ex=120)

    def _send_heartbeat(self):
        """Send periodic heartbeat to Redis."""
        now = time.time()
        if now - self._last_heartbeat < settings.WATCHDOG_INTERVAL_S / 2:
            return

        if self.redis_client:
            data = {
                "account_id": self.account_id,
                "login": self.login,
                "role": self.role,
                "connected": self.connected,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            self.redis_client.set(self._heartbeat_key, json.dumps(data), ex=settings.HEARTBEAT_STALE_S)
        self._last_heartbeat = now

    def _get_account_info(self) -> dict:
        """Fetch current account state from MT5."""
        info = mt5.account_info()
        if not info:
            return {"error": "Cannot fetch account info"}
        return {
            "login": info.login,
            "balance": info.balance,
            "equity": info.equity,
            "margin": info.margin,
            "free_margin": info.margin_free,
            "leverage": info.leverage,
            "currency": info.currency,
            "server": info.server,
            "trade_mode": info.trade_mode,
        }

    def _get_positions(self) -> list[dict]:
        """Fetch all open positions."""
        positions = mt5.positions_get()
        if not positions:
            return []
        return [
            {
                "ticket": p.ticket,
                "symbol": p.symbol,
                "type": "BUY" if p.type == 0 else "SELL",
                "volume": p.volume,
                "price_open": p.price_open,
                "price_current": p.price_current,
                "sl": p.sl,
                "tp": p.tp,
                "profit": p.profit,
                "swap": p.swap,
                "time": str(p.time),
                "comment": p.comment,
            }
            for p in positions
        ]

    def _handle_command(self, cmd: dict) -> dict:
        """Process a command received from the Terminal Pool."""
        action = cmd.get("action", "")
        request_id = cmd.get("request_id", "")

        response = {"request_id": request_id, "account_id": self.account_id, "action": action}

        try:
            if action == "ping":
                response["result"] = "pong"

            elif action == "account_info":
                response["result"] = self._get_account_info()

            elif action == "positions":
                response["result"] = self._get_positions()

            elif action == "reconnect":
                self._disconnect_mt5()
                time.sleep(1)
                success = self._connect_mt5()
                response["result"] = {"reconnected": success}

            elif action == "disconnect":
                self._disconnect_mt5()
                self.running = False
                response["result"] = {"disconnected": True}

            elif action == "update_balance":
                # Refresh balance and push to DB update queue
                info = self._get_account_info()
                if "error" not in info:
                    self.redis_client.publish("mt5mgr:balance_updates", json.dumps({
                        "account_id": self.account_id,
                        "balance": info["balance"],
                        "equity": info["equity"],
                    }))
                response["result"] = info

            else:
                response["error"] = f"Unknown command: {action}"

        except Exception as e:
            response["error"] = str(e)
            logger.error(f"[{self.login}] Command error ({action}): {e}")

        return response

    def run(self):
        """Main loop: connect, process commands, send heartbeats."""
        self.redis_client = redis.from_url(settings.REDIS_URL)
        self.running = True

        # Attempt initial connection
        if not self._connect_mt5():
            logger.error(f"[{self.login}] Initial connection failed, entering retry mode")
            # Retry with backoff
            for attempt in range(1, settings.MAX_RECONNECT_ATTEMPTS + 1):
                delay = settings.RECONNECT_BACKOFF_BASE_S * (2 ** (attempt - 1))
                logger.info(f"[{self.login}] Retry {attempt}/{settings.MAX_RECONNECT_ATTEMPTS} in {delay}s")
                time.sleep(delay)
                if self._connect_mt5():
                    break
            else:
                logger.error(f"[{self.login}] All connection attempts failed, exiting")
                self._update_status("failed")
                return

        logger.info(f"[{self.login}] Terminal process running (role={self.role})")

        while self.running:
            try:
                self._send_heartbeat()

                # Check for commands (non-blocking with 2s timeout)
                result = self.redis_client.brpop(self._cmd_queue, timeout=2)

                if result:
                    _, raw = result
                    cmd = json.loads(raw)
                    response = self._handle_command(cmd)
                    self.redis_client.lpush(self._resp_queue, json.dumps(response))

                # Verify connection is still alive (every few iterations)
                if self.connected and not mt5.terminal_info():
                    logger.warning(f"[{self.login}] Connection lost, attempting reconnect")
                    self.connected = False
                    self._update_status("reconnecting")
                    self._connect_mt5()

            except redis.ConnectionError:
                logger.error(f"[{self.login}] Redis connection lost, retrying...")
                time.sleep(5)
                try:
                    self.redis_client = redis.from_url(settings.REDIS_URL)
                except Exception:
                    pass

            except Exception as e:
                logger.error(f"[{self.login}] Process error: {e}", exc_info=True)
                time.sleep(1)

        self._disconnect_mt5()
        logger.info(f"[{self.login}] Terminal process exiting")


def subprocess_entry(account_id: str, login: int, password: str, server: str, role: str = "client"):
    """Entry point for multiprocessing.Process."""
    logging.basicConfig(
        level=logging.INFO,
        format=f"%(asctime)s [{login}] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    proc = TerminalProcess(account_id, login, password, server, role)

    def shutdown(signum, frame):
        proc.running = False

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    proc.run()
