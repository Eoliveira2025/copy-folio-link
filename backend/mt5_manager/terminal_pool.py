"""
Terminal Pool — manages the lifecycle of all MT5 terminal subprocesses.

Responsibilities:
  - Spawn/stop terminal processes
  - Track process state and PIDs
  - Send commands to terminals via Redis queues
  - Receive responses
  - Enforce MAX_TERMINALS limit
"""

from __future__ import annotations
import logging
import time
import json
import uuid
import multiprocessing
from typing import Dict, Optional
from dataclasses import dataclass, field
from enum import Enum
import redis

from mt5_manager.config import get_manager_settings
from mt5_manager.terminal_process import subprocess_entry

settings = get_manager_settings()
logger = logging.getLogger("mt5_manager.pool")


class TerminalState(str, Enum):
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass
class ManagedTerminal:
    """Metadata for a managed MT5 terminal subprocess."""
    account_id: str
    login: int
    server: str
    role: str  # "master" or "client"
    process: Optional[multiprocessing.Process] = None
    state: TerminalState = TerminalState.STOPPED
    pid: Optional[int] = None
    started_at: Optional[float] = None
    restart_count: int = 0
    last_error: Optional[str] = None


class TerminalPool:
    """Manages a pool of MT5 terminal subprocesses."""

    def __init__(self):
        self.terminals: Dict[str, ManagedTerminal] = {}  # account_id → ManagedTerminal
        self.redis_client = redis.from_url(settings.REDIS_URL)

    @property
    def active_count(self) -> int:
        return sum(1 for t in self.terminals.values() if t.state == TerminalState.RUNNING)

    def spawn_terminal(
        self,
        account_id: str,
        login: int,
        password: str,
        server: str,
        role: str = "client",
    ) -> bool:
        """Spawn a new MT5 terminal subprocess."""
        if self.active_count >= settings.MAX_TERMINALS:
            logger.error(f"Cannot spawn terminal for {login}: pool limit reached ({settings.MAX_TERMINALS})")
            return False

        if account_id in self.terminals and self.terminals[account_id].state == TerminalState.RUNNING:
            logger.warning(f"Terminal already running for {login}")
            return True

        logger.info(f"Spawning terminal for login={login} server={server} role={role}")

        proc = multiprocessing.Process(
            target=subprocess_entry,
            args=(account_id, login, password, server, role),
            name=f"MT5-{role}-{login}",
            daemon=True,
        )

        managed = ManagedTerminal(
            account_id=account_id,
            login=login,
            server=server,
            role=role,
            process=proc,
            state=TerminalState.STARTING,
            started_at=time.time(),
        )
        self.terminals[account_id] = managed

        proc.start()
        managed.pid = proc.pid
        managed.state = TerminalState.RUNNING

        logger.info(f"Terminal spawned: login={login} pid={proc.pid}")

        # Cooldown to prevent overwhelming the system
        time.sleep(settings.SPAWN_COOLDOWN_S)
        return True

    def stop_terminal(self, account_id: str, timeout: int = 10) -> bool:
        """Gracefully stop a terminal subprocess."""
        terminal = self.terminals.get(account_id)
        if not terminal or not terminal.process:
            return False

        terminal.state = TerminalState.STOPPING
        logger.info(f"Stopping terminal login={terminal.login} pid={terminal.pid}")

        # Send disconnect command via Redis
        self.send_command(account_id, "disconnect")

        # Wait for graceful shutdown
        terminal.process.join(timeout=timeout)

        if terminal.process.is_alive():
            logger.warning(f"Force killing terminal login={terminal.login}")
            terminal.process.terminate()
            terminal.process.join(timeout=5)
            if terminal.process.is_alive():
                terminal.process.kill()

        terminal.state = TerminalState.STOPPED
        terminal.process = None
        terminal.pid = None
        logger.info(f"Terminal stopped: login={terminal.login}")
        return True

    def restart_terminal(self, account_id: str, password: str) -> bool:
        """Restart a terminal subprocess."""
        terminal = self.terminals.get(account_id)
        if not terminal:
            return False

        terminal.restart_count += 1
        logger.info(f"Restarting terminal login={terminal.login} (attempt #{terminal.restart_count})")

        self.stop_terminal(account_id)
        time.sleep(2)
        return self.spawn_terminal(account_id, terminal.login, password, terminal.server, terminal.role)

    def send_command(self, account_id: str, action: str, params: dict | None = None, timeout: int = 10) -> dict | None:
        """Send a command to a terminal and wait for response."""
        request_id = str(uuid.uuid4())
        cmd = {
            "request_id": request_id,
            "action": action,
            **(params or {}),
        }

        cmd_queue = f"mt5mgr:cmd:{account_id}"
        resp_queue = f"mt5mgr:resp:{account_id}"

        self.redis_client.lpush(cmd_queue, json.dumps(cmd))

        # Wait for response
        start = time.time()
        while time.time() - start < timeout:
            result = self.redis_client.brpop(resp_queue, timeout=1)
            if result:
                _, raw = result
                response = json.loads(raw)
                if response.get("request_id") == request_id:
                    return response
            # Response not for us, push back (shouldn't happen with unique request_ids)

        logger.warning(f"Command timeout: {action} → {account_id}")
        return None

    def get_account_info(self, account_id: str) -> dict | None:
        """Query a terminal for account info."""
        response = self.send_command(account_id, "account_info")
        if response and "result" in response:
            return response["result"]
        return None

    def get_positions(self, account_id: str) -> list[dict]:
        """Query a terminal for open positions."""
        response = self.send_command(account_id, "positions")
        if response and "result" in response:
            return response["result"]
        return []

    def get_pool_status(self) -> dict:
        """Return summary of all managed terminals."""
        by_state = {}
        for t in self.terminals.values():
            state = t.state.value
            by_state[state] = by_state.get(state, 0) + 1

        return {
            "total": len(self.terminals),
            "active": self.active_count,
            "max": settings.MAX_TERMINALS,
            "by_state": by_state,
            "terminals": [
                {
                    "account_id": t.account_id,
                    "login": t.login,
                    "server": t.server,
                    "role": t.role,
                    "state": t.state.value,
                    "pid": t.pid,
                    "restart_count": t.restart_count,
                    "uptime_s": int(time.time() - t.started_at) if t.started_at else 0,
                }
                for t in self.terminals.values()
            ],
        }

    def stop_all(self):
        """Stop all terminal subprocesses."""
        logger.info(f"Stopping all terminals ({self.active_count} active)...")
        for account_id in list(self.terminals.keys()):
            self.stop_terminal(account_id, timeout=5)
        logger.info("All terminals stopped")
