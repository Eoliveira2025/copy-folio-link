"""PoolManager — Unified entry point for the new institutional V2 architecture."""

import threading
from typing import Dict, List, Optional
from uuid import UUID

from .terminal_process import PooledTerminalProcess
from .session_manager import SessionManager
from .account_context import AccountContext
from .health_monitor import HealthMonitor
from .terminal_allocator import TerminalAllocatorV2
from ..utils.logger import get_logger
from . import repo

class PoolManager:
    """Orchestrates all terminals and sessions on a single VPS."""

    def __init__(self):
        self._terminals: Dict[UUID, PooledTerminalProcess] = {}
        self._session_managers: Dict[UUID, SessionManager] = {}
        self._lock = threading.RLock()
        self.allocator = TerminalAllocatorV2()
        self.health = HealthMonitor(
            get_terminals=lambda: list(self._terminals.values()),
            get_sessions=lambda tid: self._session_managers[tid].list_sessions() if tid in self._session_managers else []
        )
        self.log = get_logger("pool_manager")

    def start(self):
        self.health.start()
        self.log.info("pool manager started")

    def stop(self):
        self.health.stop()
        with self._lock:
            for t in self._terminals.values():
                t.stop()
        self.log.info("pool manager stopped")

    def ensure_terminal(self, terminal_id: UUID, terminal_path: str) -> PooledTerminalProcess:
        """Get or create a terminal process handle."""
        with self._lock:
            if terminal_id not in self._terminals:
                t = PooledTerminalProcess(terminal_id, terminal_path)
                self._terminals[terminal_id] = t
                self._session_managers[terminal_id] = SessionManager(terminal_id)
                t.start()
            return self._terminals[terminal_id]

    def register_account(self, account_id: UUID, terminal_id: UUID, login: int, server: str):
        """Register an account session to a specific terminal."""
        with self._lock:
            if terminal_id not in self._session_managers:
                # Should have been created by ensure_terminal
                self.log.error("terminal not found for account registration", extra={"terminal_id": str(terminal_id)})
                return
            
            ctx = AccountContext(account_id=account_id, login=login, server=server)
            self._session_managers[terminal_id].add_session(ctx)

    def get_terminal(self, terminal_id: UUID) -> Optional[PooledTerminalProcess]:
        return self._terminals.get(terminal_id)

    def get_session_manager(self, terminal_id: UUID) -> Optional[SessionManager]:
        return self._session_managers.get(terminal_id)
