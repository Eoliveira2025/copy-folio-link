"""PoolManager — Institutional Gateway for V2."""

import threading
from typing import Dict, List, Optional
from uuid import UUID

from .terminal_process import PooledTerminalProcess
from .account_session import AccountSession
from .health_monitor import HealthMonitor
from .terminal_allocator import TerminalAllocatorV2
from ..utils.logger import get_logger
from . import repo

class PoolManager:
    """Orchestrates isolated terminals and sessions."""

    def __init__(self):
        self._terminals: Dict[UUID, PooledTerminalProcess] = {}
        self._sessions: Dict[UUID, AccountSession] = {}
        self._lock = threading.RLock()
        self.allocator = TerminalAllocatorV2()
        self.health = HealthMonitor(
            get_terminals=lambda: list(self._terminals.values()),
            get_sessions=lambda tid: [self._sessions[tid]] if tid in self._sessions else []
        )
        self.log = get_logger("pool_manager")

    def start(self):
        self.health.start()
        self.log.info("institutional pool manager started")

    def stop(self):
        self.health.stop()
        with self._lock:
            for t in self._terminals.values():
                t.stop()
        self.log.info("institutional pool manager stopped")

    def ensure_terminal(self, terminal_id: UUID, terminal_path: str) -> PooledTerminalProcess:
        """Get or create a terminal process handle."""
        with self._lock:
            if terminal_id not in self._terminals:
                t = PooledTerminalProcess(terminal_id, terminal_path)
                self._terminals[terminal_id] = t
                # One session per terminal
                s = AccountSession(
                    pool_id=terminal_id,
                    terminal_id=terminal_id,
                    terminal_path=terminal_path,
                    account_details_loader=repo.get_account_details
                )
                self._sessions[terminal_id] = s
                t.start()
            return self._terminals[terminal_id]

    def get_terminal(self, terminal_id: UUID) -> Optional[PooledTerminalProcess]:
        return self._terminals.get(terminal_id)

    def get_session(self, terminal_id: UUID) -> Optional[AccountSession]:
        return self._sessions.get(terminal_id)

    def reconnect_account(self, terminal_id: UUID) -> bool:
        """Force a terminal restart and session login."""
        with self._lock:
            terminal = self.get_terminal(terminal_id)
            if terminal:
                self.log.info("triggering manual reconnect", extra={"terminal_id": str(terminal_id)})
                terminal.stop()
                time.sleep(1) # Allow for cleanup
                terminal.start()
                return True
        return False

    def recycle_terminal(self, terminal_id: UUID) -> bool:
        """Recycle a terminal to clear memory/cache."""
        with self._lock:
            terminal = self.get_terminal(terminal_id)
            if terminal:
                self.log.info("triggering manual recycle", extra={"terminal_id": str(terminal_id)})
                terminal.recycle() # Assuming recycle() is implemented in terminal_process
                return True
        return False

    def remove_account(self, terminal_id: UUID, force: bool = False) -> bool:
        """Safely remove an account from the pool."""
        with self._lock:
            session = self.get_session(terminal_id)
            if session and not force:
                # Check for open positions if not forced
                if session.has_open_positions():
                    self.log.warning("refusing to remove account with open positions", extra={"terminal_id": str(terminal_id)})
                    return False

            terminal = self.get_terminal(terminal_id)
            if terminal:
                terminal.stop()
                del self._terminals[terminal_id]
                if terminal_id in self._sessions:
                    del self._sessions[terminal_id]
                self.log.info("account removed from pool", extra={"terminal_id": str(terminal_id)})
                return True
        return False


