"""Scheduled task to create daily trade partitions ahead of time."""

import logging
from datetime import date, timedelta
from sqlalchemy import create_engine, text
from app.core.config import get_settings

logger = logging.getLogger("app.partition_manager")
settings = get_settings()


def create_daily_partitions(days_ahead: int = 7):
    """Create trade_events and trade_copies partitions for the next N days."""
    engine = create_engine(settings.DATABASE_URL_SYNC)

    with engine.connect() as conn:
        for i in range(days_ahead):
            d = date.today() + timedelta(days=i)
            d_next = d + timedelta(days=1)
            suffix = d.strftime("%Y_%m_%d")

            for table in ("trade_events", "trade_copies"):
                part_name = f"{table}_{suffix}"
                try:
                    conn.execute(text(f"""
                        CREATE TABLE IF NOT EXISTS {part_name}
                        PARTITION OF {table}
                        FOR VALUES FROM ('{d}') TO ('{d_next}')
                    """))
                except Exception:
                    pass  # Already exists

        conn.commit()

    logger.info(f"Ensured partitions exist for next {days_ahead} days")
