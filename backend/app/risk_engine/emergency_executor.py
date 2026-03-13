"""
Emergency Executor — closes all open trades across all MT5 accounts.

Dispatches emergency close commands via Redis and sets system state
to EMERGENCY_STOP in the database.
"""

import logging
import json
from datetime import datetime, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
import redis

from app.core.config import get_settings

logger = logging.getLogger("risk_engine.executor")
settings = get_settings()


class EmergencyExecutor:
    """Executes the emergency close sequence across all trading infrastructure."""

    _db_engine = None
    _redis_client = None

    @classmethod
    def _get_db(cls):
        if cls._db_engine is None:
            cls._db_engine = create_engine(
                settings.DATABASE_URL_SYNC, pool_size=5, pool_pre_ping=True
            )
        return cls._db_engine

    @classmethod
    def _get_redis(cls):
        if cls._redis_client is None:
            cls._redis_client = redis.from_url(settings.REDIS_URL)
        return cls._redis_client

    @classmethod
    def execute_emergency_close(cls):
        """
        Close all open trades on all connected MT5 accounts.
        Non-blocking, idempotent — uses Redis SETNX to prevent duplicate execution.
        """
        r = cls._get_redis()

        # Idempotency guard: only one emergency close per incident
        if not r.set("copytrade:emergency_close_lock", "1", nx=True, ex=300):
            logger.warning("Emergency close already in progress — skipping duplicate")
            return

        logger.critical("Executing EMERGENCY CLOSE on all accounts")

        engine = cls._get_db()

        # 1. Fetch all connected MT5 accounts
        with Session(engine) as db:
            accounts = db.execute(text("""
                SELECT id, login, server
                FROM mt5_accounts
                WHERE status = 'connected'
            """)).fetchall()

        if not accounts:
            logger.warning("No connected accounts found for emergency close")
            return

        # 2. Send emergency close command to each account via Redis
        pipe = r.pipeline(transaction=False)
        timestamp = datetime.now(timezone.utc).isoformat()

        for account in accounts:
            account_id = str(account.id)
            command = {
                "action": "emergency_close_all",
                "account_id": account_id,
                "login": account.login,
                "server": account.server,
                "timestamp": timestamp,
                "reason": "GLOBAL_DRAWDOWN_BREACH",
            }

            # Push to the account's execution queue
            pipe.lpush(f"copytrade:execute:{account_id}", json.dumps(command))

            # Also publish on the emergency channel for immediate handling
            pipe.publish("copytrade:emergency_close", json.dumps(command))

        pipe.execute()

        logger.critical(f"Emergency close dispatched to {len(accounts)} accounts")

        # 3. Set system state to EMERGENCY_STOP
        with Session(engine) as db:
            db.execute(text("""
                UPDATE system_settings
                SET protection_enabled = false, updated_at = :now
            """), {"now": datetime.now(timezone.utc)})

            # Also update a system_state key in Redis for fast checks
            r.set("copytrade:system_state", "EMERGENCY_STOP")

            db.commit()

        # 4. Block new trades by setting a Redis flag (no expiry — must be manually cleared)
        r.set("copytrade:trading_blocked", "1")

        logger.critical(f"System state set to EMERGENCY_STOP — all new trades blocked, {len(accounts)} accounts notified")
