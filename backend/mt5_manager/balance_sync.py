"""
Balance Sync — listens for balance update events and persists them to the database.
Runs as a background thread.
"""

from __future__ import annotations
import json
import logging
import threading
import redis
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from mt5_manager.config import get_manager_settings

settings = get_manager_settings()
logger = logging.getLogger("mt5_manager.balance_sync")


class BalanceSync(threading.Thread):
    """Subscribes to balance updates from terminal processes and writes to DB."""

    def __init__(self):
        super().__init__(daemon=True, name="BalanceSync")
        self.running = False
        self.redis_client = redis.from_url(settings.REDIS_URL)
        self.db_engine = create_engine(settings.DATABASE_URL_SYNC)

    def run(self):
        self.running = True
        pubsub = self.redis_client.pubsub()
        pubsub.subscribe("mt5mgr:balance_updates")

        logger.info("Balance Sync started")

        for message in pubsub.listen():
            if not self.running:
                break
            if message["type"] != "message":
                continue

            try:
                data = json.loads(message["data"])
                account_id = data["account_id"]
                balance = data["balance"]
                equity = data["equity"]

                with Session(self.db_engine) as db:
                    db.execute(text("""
                        UPDATE mt5_accounts
                        SET balance = :balance, equity = :equity, last_connected_at = :now
                        WHERE id = :id
                    """), {
                        "balance": balance,
                        "equity": equity,
                        "now": datetime.now(timezone.utc),
                        "id": account_id,
                    })
                    db.commit()

            except Exception as e:
                logger.error(f"Balance sync error: {e}")

    def stop(self):
        self.running = False


class FailureHandler(threading.Thread):
    """Subscribes to terminal failure events and updates DB account status."""

    def __init__(self):
        super().__init__(daemon=True, name="FailureHandler")
        self.running = False
        self.redis_client = redis.from_url(settings.REDIS_URL)
        self.db_engine = create_engine(settings.DATABASE_URL_SYNC)

    def run(self):
        self.running = True
        pubsub = self.redis_client.pubsub()
        pubsub.subscribe("mt5mgr:failures")

        logger.info("Failure Handler started")

        for message in pubsub.listen():
            if not self.running:
                break
            if message["type"] != "message":
                continue

            try:
                data = json.loads(message["data"])
                account_id = data["account_id"]

                with Session(self.db_engine) as db:
                    db.execute(text("""
                        UPDATE mt5_accounts
                        SET status = 'disconnected'
                        WHERE id = :id
                    """), {"id": account_id})
                    db.commit()

                logger.warning(f"Marked account {account_id} as disconnected: {data.get('reason')}")

            except Exception as e:
                logger.error(f"Failure handler error: {e}")

    def stop(self):
        self.running = False
