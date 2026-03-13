"""
Terminal Pool — manages the lifecycle of pooled MT5 terminal subprocesses.

Architecture change: Each terminal process can now manage MULTIPLE accounts.
The TerminalAllocator assigns accounts to terminals, and commands are routed
through Redis queues keyed by terminal_id (not account_id).

Responsibilities:
  - Spawn/stop terminal processes (each can handle up to 50 accounts)
  - Track process state, PIDs, and account assignments
  - Send per-account commands through terminal-level Redis queues
  - Auto-spawn new terminals when capacity is exceeded
  - Enforce MAX_TERMINALS limit
"""

from __future__ import annotations
import logging
import time
import json
import uuid
import multiprocessing
from typing import Dict, Optional, Set
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
    terminal_id: str
    process: Optional[multiprocessing.Process] = None
    state: TerminalState = TerminalState.STOPPED
    pid: Optional[int] = None
    started_at: Optional[float] = None
    restart_count: int = 0
    last_error: Optional[str] = None
    # Multi-account: track which accounts are loaded in this terminal
    accounts: Set[str] = field(default_factory=set)
    account_logins: Dict[str, int] = field(default_factory=dict)  # account_id → login

    @property
    def account_count(self) -> int:
        return len(self.accounts)


class TerminalPool:
    """Manages a pool of MT5 terminal subprocesses, each serving multiple accounts."""

    def __init__(self):
        self.terminals: Dict[str, ManagedTerminal] = {}  # terminal_id → ManagedTerminal
        self.account_terminal_map: Dict[str, str] = {}  # account_id → terminal_id
        self.redis_client = redis.from_url(settings.REDIS_URL)

    @property
    def active_count(self) -> int:
        return sum(1 for t in self.terminals.values() if t.state == TerminalState.RUNNING)

    @property
    def total_accounts(self) -> int:
        return sum(t.account_count for t in self.terminals.values())

    @property
    def total_capacity(self) -> int:
        return settings.MAX_TERMINALS * settings.MAX_ACCOUNTS_PER_TERMINAL

    def spawn_terminal(self, terminal_id: Optional[str] = None) -> Optional[str]:
        """Spawn a new pooled MT5 terminal subprocess. Returns terminal_id."""
        if self.active_count >= settings.MAX_TERMINALS:
            logger.error(f"Cannot spawn terminal: pool limit reached ({settings.MAX_TERMINALS})")
            return None

        if terminal_id is None:
            terminal_id = f"term-{uuid.uuid4().hex[:8]}"

        if terminal_id in self.terminals and self.terminals[terminal_id].state == TerminalState.RUNNING:
            logger.warning(f"Terminal {terminal_id} already running")
            return terminal_id

        logger.info(f"Spawning pooled terminal {terminal_id}")

        proc = multiprocessing.Process(
            target=subprocess_entry,
            args=(terminal_id,),
            name=f"MT5-Pool-{terminal_id}",
            daemon=True,
        )

        managed = ManagedTerminal(
            terminal_id=terminal_id,
            process=proc,
            state=TerminalState.STARTING,
            started_at=time.time(),
        )
        self.terminals[terminal_id] = managed

        proc.start()
        managed.pid = proc.pid
        managed.state = TerminalState.RUNNING

        logger.info(f"Terminal spawned: {terminal_id} pid={proc.pid}")

        time.sleep(settings.SPAWN_COOLDOWN_S)
        return terminal_id

    def stop_terminal(self, terminal_id: str, timeout: int = 10) -> bool:
        """Gracefully stop a terminal subprocess."""
        terminal = self.terminals.get(terminal_id)
        if not terminal or not terminal.process:
            return False

        terminal.state = TerminalState.STOPPING
        logger.info(f"Stopping terminal {terminal_id} pid={terminal.pid}")

        # Send shutdown command
        self._send_terminal_command(terminal_id, "shutdown")

        terminal.process.join(timeout=timeout)

        if terminal.process.is_alive():
            logger.warning(f"Force killing terminal {terminal_id}")
            terminal.process.terminate()
            terminal.process.join(timeout=5)
            if terminal.process.is_alive():
                terminal.process.kill()

        # Clean up account mappings
        for account_id in list(terminal.accounts):
            self.account_terminal_map.pop(account_id, None)

        terminal.state = TerminalState.STOPPED
        terminal.process = None
        terminal.pid = None
        terminal.accounts.clear()
        logger.info(f"Terminal stopped: {terminal_id}")
        return True

    def add_account_to_terminal(
        self,
        terminal_id: str,
        account_id: str,
        login: int,
        password: str,
        server: str,
        role: str = "client",
    ) -> bool:
        """Add an MT5 account to a running terminal process."""
        terminal = self.terminals.get(terminal_id)
        if not terminal or terminal.state != TerminalState.RUNNING:
            logger.error(f"Terminal {terminal_id} not running, cannot add account")
            return False

        if terminal.account_count >= settings.MAX_ACCOUNTS_PER_TERMINAL:
            logger.error(f"Terminal {terminal_id} full ({terminal.account_count} accounts)")
            return False

        # Send login command to the terminal process via Redis
        response = self._send_account_command(terminal_id, account_id, "login", {
            "login": login,
            "password": password,
            "server": server,
            "role": role,
        })

        if response and response.get("status") == "ok":
            terminal.accounts.add(account_id)
            terminal.account_logins[account_id] = login
            self.account_terminal_map[account_id] = terminal_id
            logger.info(f"Account {login} added to terminal {terminal_id}")
            return True

        logger.error(f"Failed to add account {login} to terminal {terminal_id}: {response}")
        return False

    def remove_account_from_terminal(self, account_id: str) -> bool:
        """Remove an MT5 account from its terminal."""
        terminal_id = self.account_terminal_map.get(account_id)
        if not terminal_id:
            return False

        terminal = self.terminals.get(terminal_id)
        if not terminal:
            return False

        self._send_account_command(terminal_id, account_id, "disconnect")

        terminal.accounts.discard(account_id)
        terminal.account_logins.pop(account_id, None)
        self.account_terminal_map.pop(account_id, None)

        logger.info(f"Account removed from terminal {terminal_id}")
        return True

    def send_trade_command(self, account_id: str, action: str, params: dict = None) -> Optional[dict]:
        """Send a trade command to a specific account through its terminal."""
        terminal_id = self.account_terminal_map.get(account_id)
        if not terminal_id:
            logger.error(f"No terminal found for account {account_id}")
            return None

        return self._send_account_command(terminal_id, account_id, action, params)

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
            "total_accounts": self.total_accounts,
            "total_capacity": self.total_capacity,
            "utilization": f"{self.total_accounts / max(1, self.total_capacity):.0%}",
            "by_state": by_state,
            "terminals": [
                {
                    "terminal_id": t.terminal_id,
                    "state": t.state.value,
                    "pid": t.pid,
                    "accounts": t.account_count,
                    "max_accounts": settings.MAX_ACCOUNTS_PER_TERMINAL,
                    "restart_count": t.restart_count,
                    "uptime_s": int(time.time() - t.started_at) if t.started_at else 0,
                }
                for t in self.terminals.values()
            ],
        }

    def find_available_terminal(self) -> Optional[str]:
        """Find a running terminal with available capacity, or spawn a new one."""
        for t in self.terminals.values():
            if t.state == TerminalState.RUNNING and t.account_count < settings.MAX_ACCOUNTS_PER_TERMINAL:
                return t.terminal_id

        # No available terminal, spawn a new one
        return self.spawn_terminal()

    def restart_terminal(self, terminal_id: str) -> bool:
        """Non-blocking restart of a terminal, preserving its account list for re-login."""
        terminal = self.terminals.get(terminal_id)
        if not terminal:
            return False

        terminal.restart_count += 1
        orphaned_accounts = list(terminal.accounts)

        import threading

        def _do_restart():
            self.stop_terminal(terminal_id)
            time.sleep(2)
            new_id = self.spawn_terminal(terminal_id)
            if new_id:
                logger.info(f"Terminal {terminal_id} restarted, {len(orphaned_accounts)} accounts need re-login")
                for account_id in orphaned_accounts:
                    self.redis_client.publish("mt5mgr:provision", json.dumps({
                        "action": "reconnect",
                        "account_id": account_id,
                        "terminal_id": new_id,
                    }))
            else:
                logger.error(f"Terminal {terminal_id} restart failed")

        restart_thread = threading.Thread(
            target=_do_restart, name=f"restart-{terminal_id}", daemon=True
        )
        restart_thread.start()
        logger.info(f"Terminal {terminal_id} restart initiated (non-blocking)")
        return True

    def stop_all(self):
        """Stop all terminal subprocesses."""
        logger.info(f"Stopping all terminals ({self.active_count} active)...")
        for terminal_id in list(self.terminals.keys()):
            self.stop_terminal(terminal_id, timeout=5)
        logger.info("All terminals stopped")

    # ── Private ──────────────────────────────────────────────────────

    def _send_terminal_command(self, terminal_id: str, action: str, params: dict = None) -> Optional[dict]:
        """Send a command to a terminal process."""
        request_id = str(uuid.uuid4())
        cmd = {"request_id": request_id, "action": action, **(params or {})}
        cmd_queue = f"mt5pool:cmd:{terminal_id}"
        resp_queue = f"mt5pool:resp:{terminal_id}"

        self.redis_client.lpush(cmd_queue, json.dumps(cmd))

        start = time.time()
        while time.time() - start < 15:
            result = self.redis_client.brpop(resp_queue, timeout=1)
            if result:
                _, raw = result
                response = json.loads(raw)
                if response.get("request_id") == request_id:
                    return response
        return None

    def _send_account_command(
        self, terminal_id: str, account_id: str, action: str, params: dict = None
    ) -> Optional[dict]:
        """Send a command targeting a specific account within a terminal."""
        full_params = {"account_id": account_id, **(params or {})}
        return self._send_terminal_command(terminal_id, action, full_params)
