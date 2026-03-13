"""
Account Session Manager — manages individual MT5 account sessions within pooled terminals.

Each session represents a logged-in MT5 account with:
  - Connection state tracking
  - Automatic reconnection with exponential backoff
  - Strategy subscription management
  - Balance/equity caching
  - Session lifecycle events published to Redis

Redis keys:
  mt5sess:{account_id}:state     → JSON session state
  mt5sess:{account_id}:heartbeat → timestamp (TTL-based)
"""

from __future__ import annotations
import logging
import json
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Optional, Callable
import threading
import redis

from mt5_manager.config import get_manager_settings

settings = get_manager_settings()
logger = logging.getLogger("mt5_manager.session")


class SessionState(str, Enum):
    PENDING = "pending"           # Waiting for terminal assignment
    CONNECTING = "connecting"     # MT5 login in progress
    ACTIVE = "active"             # Connected and operational
    RECONNECTING = "reconnecting" # Lost connection, attempting recovery
    SUSPENDED = "suspended"       # Admin-suspended or billing issue
    DISCONNECTED = "disconnected" # Cleanly disconnected
    FAILED = "failed"             # Unrecoverable error


@dataclass
class AccountSession:
    """Represents a live MT5 account session."""
    account_id: str
    user_id: str
    login: int
    server: str
    strategy_level: str
    terminal_id: Optional[str] = None  # Assigned pooled terminal
    state: SessionState = SessionState.PENDING
    connected_at: Optional[str] = None
    last_heartbeat: Optional[str] = None
    balance: float = 0.0
    equity: float = 0.0
    margin_free: float = 0.0
    leverage: int = 0
    reconnect_count: int = 0
    max_reconnects: int = 10
    last_error: Optional[str] = None
    master_account_id: Optional[str] = None  # Subscribed master

    def to_dict(self) -> dict:
        d = asdict(self)
        d["state"] = self.state.value
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "AccountSession":
        d["state"] = SessionState(d["state"])
        return cls(**d)


class SessionManager:
    """
    Manages all active account sessions across pooled terminals.

    Responsibilities:
      - Track session lifecycle (connect → active → disconnect)
      - Coordinate with TerminalAllocator for terminal assignment
      - Manage strategy subscriptions (master account mapping)
      - Handle reconnection logic with backoff
      - Publish session events for dashboard/monitoring
    """

    def __init__(self):
        self.sessions: Dict[str, AccountSession] = {}  # account_id → session
        self.redis_client = redis.from_url(settings.REDIS_URL)
        self._lock = threading.Lock()
        self._strategy_master_map: Dict[str, str] = {}  # strategy_level → master_account_id
        self._refresh_strategy_map()

    def _refresh_strategy_map(self):
        """Load strategy → master account mapping from Redis or DB."""
        try:
            raw = self.redis_client.get("mt5mgr:strategy_master_map")
            if raw:
                self._strategy_master_map = json.loads(raw)
                logger.info(f"Strategy map loaded: {self._strategy_master_map}")
        except Exception as e:
            logger.warning(f"Could not load strategy map: {e}")

    def update_strategy_map(self, mapping: Dict[str, str]):
        """Update strategy → master account mapping."""
        self._strategy_master_map = mapping
        self.redis_client.set("mt5mgr:strategy_master_map", json.dumps(mapping))
        logger.info(f"Strategy map updated: {mapping}")

    def create_session(
        self,
        account_id: str,
        user_id: str,
        login: int,
        server: str,
        strategy_level: str,
    ) -> AccountSession:
        """Create a new account session (pending terminal assignment)."""
        with self._lock:
            if account_id in self.sessions:
                existing = self.sessions[account_id]
                if existing.state in (SessionState.ACTIVE, SessionState.CONNECTING):
                    logger.warning(f"Session already exists for {login}, returning existing")
                    return existing

            master_id = self._strategy_master_map.get(strategy_level)

            session = AccountSession(
                account_id=account_id,
                user_id=user_id,
                login=login,
                server=server,
                strategy_level=strategy_level,
                master_account_id=master_id,
            )
            self.sessions[account_id] = session
            self._publish_state(session)

            logger.info(f"Session created: login={login} strategy={strategy_level} master={master_id}")
            return session

    def activate_session(self, account_id: str, terminal_id: str, balance: float = 0, equity: float = 0):
        """Mark session as active after successful MT5 login."""
        with self._lock:
            session = self.sessions.get(account_id)
            if not session:
                return

            session.state = SessionState.ACTIVE
            session.terminal_id = terminal_id
            session.connected_at = datetime.now(timezone.utc).isoformat()
            session.balance = balance
            session.equity = equity
            session.reconnect_count = 0
            session.last_error = None
            self._publish_state(session)

            logger.info(f"Session activated: login={session.login} terminal={terminal_id}")

    def update_session_balance(self, account_id: str, balance: float, equity: float, margin_free: float = 0):
        """Update cached balance/equity from heartbeat data."""
        session = self.sessions.get(account_id)
        if not session:
            return
        session.balance = balance
        session.equity = equity
        session.margin_free = margin_free
        session.last_heartbeat = datetime.now(timezone.utc).isoformat()

    def mark_reconnecting(self, account_id: str, error: str = ""):
        """Mark session as reconnecting."""
        with self._lock:
            session = self.sessions.get(account_id)
            if not session:
                return

            session.state = SessionState.RECONNECTING
            session.reconnect_count += 1
            session.last_error = error
            self._publish_state(session)

            if session.reconnect_count >= session.max_reconnects:
                self.mark_failed(account_id, "Max reconnection attempts exceeded")

    def mark_failed(self, account_id: str, error: str = ""):
        """Mark session as permanently failed."""
        with self._lock:
            session = self.sessions.get(account_id)
            if not session:
                return

            session.state = SessionState.FAILED
            session.last_error = error
            self._publish_state(session)

            # Notify API to update DB
            self.redis_client.publish("mt5mgr:failures", json.dumps({
                "account_id": account_id,
                "login": session.login,
                "server": session.server,
                "reason": error,
                "reconnect_count": session.reconnect_count,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }))

            logger.error(f"Session failed: login={session.login} error={error}")

    def suspend_session(self, account_id: str, reason: str = "billing"):
        """Suspend a session (e.g., unpaid invoice)."""
        with self._lock:
            session = self.sessions.get(account_id)
            if not session:
                return

            session.state = SessionState.SUSPENDED
            session.last_error = f"Suspended: {reason}"
            self._publish_state(session)

            # Send disconnect command to terminal
            self.redis_client.publish("mt5mgr:provision", json.dumps({
                "action": "disconnect",
                "account_id": account_id,
            }))

            logger.info(f"Session suspended: login={session.login} reason={reason}")

    def disconnect_session(self, account_id: str):
        """Cleanly disconnect a session."""
        with self._lock:
            session = self.sessions.get(account_id)
            if not session:
                return

            session.state = SessionState.DISCONNECTED
            self._publish_state(session)

            logger.info(f"Session disconnected: login={session.login}")

    def remove_session(self, account_id: str):
        """Remove session from tracking entirely."""
        with self._lock:
            session = self.sessions.pop(account_id, None)
            if session:
                self.redis_client.delete(
                    f"mt5sess:{account_id}:state",
                    f"mt5sess:{account_id}:heartbeat",
                )
                logger.info(f"Session removed: login={session.login}")

    def change_strategy(self, account_id: str, new_strategy: str) -> bool:
        """
        Change a session's strategy subscription.
        Updates master account mapping and notifies the copy engine.
        """
        with self._lock:
            session = self.sessions.get(account_id)
            if not session:
                return False

            old_strategy = session.strategy_level
            new_master = self._strategy_master_map.get(new_strategy)

            session.strategy_level = new_strategy
            session.master_account_id = new_master
            self._publish_state(session)

            # Notify copy engine to resubscribe
            self.redis_client.publish("copytrade:strategy_change", json.dumps({
                "account_id": account_id,
                "login": session.login,
                "old_strategy": old_strategy,
                "new_strategy": new_strategy,
                "old_master": self._strategy_master_map.get(old_strategy),
                "new_master": new_master,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }))

            logger.info(
                f"Strategy changed: login={session.login} "
                f"{old_strategy} → {new_strategy} (master: {new_master})"
            )
            return True

    def get_session(self, account_id: str) -> Optional[AccountSession]:
        return self.sessions.get(account_id)

    def get_active_sessions(self) -> list[AccountSession]:
        return [s for s in self.sessions.values() if s.state == SessionState.ACTIVE]

    def get_sessions_by_strategy(self, strategy_level: str) -> list[AccountSession]:
        return [s for s in self.sessions.values() if s.strategy_level == strategy_level]

    def get_sessions_by_terminal(self, terminal_id: str) -> list[AccountSession]:
        return [s for s in self.sessions.values() if s.terminal_id == terminal_id]

    def get_session_summary(self) -> dict:
        """Return overview for monitoring."""
        by_state = {}
        by_strategy = {}
        for s in self.sessions.values():
            by_state[s.state.value] = by_state.get(s.state.value, 0) + 1
            by_strategy[s.strategy_level] = by_strategy.get(s.strategy_level, 0) + 1

        return {
            "total": len(self.sessions),
            "by_state": by_state,
            "by_strategy": by_strategy,
            "active": sum(1 for s in self.sessions.values() if s.state == SessionState.ACTIVE),
        }

    def get_reconnect_delay(self, account_id: str) -> float:
        """Calculate exponential backoff delay for reconnection."""
        session = self.sessions.get(account_id)
        if not session:
            return settings.RECONNECT_BACKOFF_BASE_S

        delay = settings.RECONNECT_BACKOFF_BASE_S * (2 ** min(session.reconnect_count, 6))
        return min(delay, 120.0)  # Cap at 2 minutes

    # ── Private ──────────────────────────────────────────────────────

    def _publish_state(self, session: AccountSession):
        """Persist session state to Redis and publish event."""
        try:
            state_data = session.to_dict()
            self.redis_client.set(
                f"mt5sess:{session.account_id}:state",
                json.dumps(state_data),
                ex=600,  # 10 min TTL
            )
            self.redis_client.publish("mt5mgr:session_events", json.dumps({
                "event": "state_change",
                "account_id": session.account_id,
                "login": session.login,
                "state": session.state.value,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }))
        except Exception as e:
            logger.error(f"Failed to publish session state: {e}")
