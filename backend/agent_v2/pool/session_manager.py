"""SessionManager — Manages multiple AccountContexts within a single PooledTerminalProcess."""

import threading
from typing import Dict, Optional, List
from uuid import UUID

from .account_context import AccountContext
from ..utils.logger import get_logger

class SessionManager:
    """Manages AccountContexts for a specific terminal.
    
    This replaces the 1-to-1 mapping of AccountSession to TerminalPool.
    In the new architecture, one terminal can have multiple sessions.
    """

    def __init__(self, terminal_id: UUID):
        self.terminal_id = terminal_id
        self._sessions: Dict[UUID, AccountContext] = {}
        self._lock = threading.RLock()
        self.log = get_logger("session_manager").bind(terminal_id=str(terminal_id))

    def add_session(self, context: AccountContext):
        with self._lock:
            self._sessions[context.account_id] = context
            self.log.info("session added", extra={"account_id": str(context.account_id)})

    def remove_session(self, account_id: UUID) -> Optional[AccountContext]:
        with self._lock:
            ctx = self._sessions.pop(account_id, None)
            if ctx:
                self.log.info("session removed", account_id=str(account_id))
            return ctx

    def get_session(self, account_id: UUID) -> Optional[AccountContext]:
        with self._lock:
            return self._sessions.get(account_id)

    def list_sessions(self) -> List[AccountContext]:
        with self._lock:
            return list(self._sessions.values())

    def get_active_count(self) -> int:
        with self._lock:
            return len(self._sessions)

    def get_metrics(self) -> Dict:
        with self._lock:
            return {
                "active_sessions": len(self._sessions),
                "sessions": {str(aid): ctx.get_metrics() for aid, ctx in self._sessions.items()}
            }
