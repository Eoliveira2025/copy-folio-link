"""
Risk Monitor — polls all MT5 account equity every 2 seconds.

Computes global drawdown and triggers EmergencyExecutor when threshold breached.
"""

import logging
import time
import threading
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.config import get_settings

logger = logging.getLogger("risk_engine.monitor")
settings = get_settings()


class RiskMonitor(threading.Thread):
    """Background thread that monitors aggregate equity across all MT5 accounts."""

    def __init__(self, poll_interval_s: float = 2.0):
        super().__init__(daemon=True, name="RiskMonitor")
        self.poll_interval_s = poll_interval_s
        self.running = False
        self.db_engine = create_engine(
            settings.DATABASE_URL_SYNC,
            pool_size=5,
            pool_pre_ping=True,
        )
        self._last_snapshot = {
            "total_balance": 0.0,
            "total_equity": 0.0,
            "drawdown_percent": 0.0,
            "account_count": 0,
        }

    @property
    def last_snapshot(self) -> dict:
        return self._last_snapshot.copy()

    def _fetch_aggregates(self) -> dict:
        """Fetch total balance and equity from all connected MT5 accounts."""
        with Session(self.db_engine) as db:
            row = db.execute(text("""
                SELECT
                    COALESCE(SUM(balance), 0) AS total_balance,
                    COALESCE(SUM(equity), 0) AS total_equity,
                    COUNT(*) AS account_count
                FROM mt5_accounts
                WHERE status = 'connected'
            """)).fetchone()

            return {
                "total_balance": float(row.total_balance),
                "total_equity": float(row.total_equity),
                "account_count": int(row.account_count),
            }

    def _fetch_protection_settings(self) -> dict | None:
        """Fetch global protection settings from system_settings table."""
        with Session(self.db_engine) as db:
            row = db.execute(text("""
                SELECT global_max_drawdown_percent, protection_enabled
                FROM system_settings
                ORDER BY created_at DESC
                LIMIT 1
            """)).fetchone()

            if not row:
                return None

            return {
                "max_drawdown_percent": float(row.global_max_drawdown_percent),
                "protection_enabled": bool(row.protection_enabled),
            }

    def run(self):
        self.running = True
        logger.info(f"RiskMonitor started (poll every {self.poll_interval_s}s)")

        while self.running:
            try:
                aggregates = self._fetch_aggregates()
                total_balance = aggregates["total_balance"]
                total_equity = aggregates["total_equity"]

                if total_balance > 0:
                    drawdown_percent = ((total_balance - total_equity) / total_balance) * 100
                else:
                    drawdown_percent = 0.0

                self._last_snapshot = {
                    "total_balance": total_balance,
                    "total_equity": total_equity,
                    "drawdown_percent": round(drawdown_percent, 2),
                    "account_count": aggregates["account_count"],
                }

                # Check protection threshold
                protection = self._fetch_protection_settings()
                if protection and protection["protection_enabled"]:
                    if drawdown_percent >= protection["max_drawdown_percent"]:
                        logger.critical(
                            f"GLOBAL DRAWDOWN BREACH: {drawdown_percent:.2f}% >= "
                            f"{protection['max_drawdown_percent']}% — triggering emergency"
                        )
                        from app.risk_engine.global_equity_guard import GlobalEquityGuard
                        GlobalEquityGuard.trigger_emergency(
                            drawdown_percent=drawdown_percent,
                            total_balance=total_balance,
                            total_equity=total_equity,
                        )

            except Exception as e:
                logger.error(f"RiskMonitor error: {e}", exc_info=True)

            time.sleep(self.poll_interval_s)

    def stop(self):
        self.running = False
        logger.info("RiskMonitor stopped")
