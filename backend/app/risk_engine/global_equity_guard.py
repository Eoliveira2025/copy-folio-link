"""
Global Equity Guard — orchestrates the emergency response.

Thread-safe, idempotent emergency trigger. Uses a lock + state flag
to prevent duplicate emergency actions.
"""

import logging
import threading
from datetime import datetime, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
import redis

from app.core.config import get_settings

logger = logging.getLogger("risk_engine.guard")
settings = get_settings()


class GlobalEquityGuard:
    """Singleton-style emergency coordinator. All methods are class-level."""

    _lock = threading.Lock()
    _emergency_active = False
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
    def is_emergency_active(cls) -> bool:
        return cls._emergency_active

    @classmethod
    def trigger_emergency(
        cls,
        drawdown_percent: float,
        total_balance: float,
        total_equity: float,
    ):
        """
        Idempotent emergency trigger.
        Only executes once — subsequent calls are no-ops until reset.
        """
        with cls._lock:
            if cls._emergency_active:
                logger.warning("Emergency already active — skipping duplicate trigger")
                return

            cls._emergency_active = True

        logger.critical("=" * 60)
        logger.critical("  GLOBAL EMERGENCY PROTECTION TRIGGERED")
        logger.critical(f"  Drawdown: {drawdown_percent:.2f}%")
        logger.critical(f"  Balance:  ${total_balance:,.2f}")
        logger.critical(f"  Equity:   ${total_equity:,.2f}")
        logger.critical("=" * 60)

        # 1. Log incident to database
        cls._log_incident(drawdown_percent, total_balance, total_equity)

        # 2. Execute emergency close via EmergencyExecutor
        from app.risk_engine.emergency_executor import EmergencyExecutor
        EmergencyExecutor.execute_emergency_close()

        # 3. Publish system emergency event
        try:
            r = cls._get_redis()
            import json
            r.publish("copytrade:system_emergency", json.dumps({
                "event": "EMERGENCY_STOP",
                "drawdown_percent": drawdown_percent,
                "total_balance": total_balance,
                "total_equity": total_equity,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }))
        except Exception as e:
            logger.error(f"Failed to publish emergency event: {e}")

        logger.critical("Emergency protection sequence completed")

    @classmethod
    def _log_incident(cls, drawdown_percent: float, total_balance: float, total_equity: float):
        """Persist incident record to risk_incidents table."""
        try:
            engine = cls._get_db()
            with Session(engine) as db:
                db.execute(text("""
                    INSERT INTO risk_incidents (incident_type, drawdown_percent, total_balance, total_equity)
                    VALUES (:incident_type, :drawdown, :balance, :equity)
                """), {
                    "incident_type": "GLOBAL_DRAWDOWN_BREACH",
                    "drawdown": drawdown_percent,
                    "balance": total_balance,
                    "equity": total_equity,
                })
                db.commit()
            logger.info("Risk incident logged to database")
        except Exception as e:
            logger.error(f"Failed to log risk incident: {e}")

    @classmethod
    def reset_emergency(cls):
        """Admin-callable reset to re-enable trading after emergency."""
        with cls._lock:
            cls._emergency_active = False
        logger.info("Emergency state reset by admin")
