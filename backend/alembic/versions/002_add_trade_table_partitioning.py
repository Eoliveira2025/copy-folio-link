"""add trade table partitioning

Revision ID: 002
Revises: 001
Create Date: 2026-03-13
"""
from typing import Sequence, Union

from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create a partitioned version of trade_events using range on timestamp
    # Step 1: Rename original table
    op.execute("ALTER TABLE trade_events RENAME TO trade_events_old")

    # Step 2: Create partitioned table with same schema
    op.execute("""
        CREATE TABLE trade_events (
            id UUID NOT NULL,
            master_account_id UUID NOT NULL REFERENCES master_accounts(id),
            ticket BIGINT NOT NULL,
            symbol VARCHAR(20) NOT NULL,
            action VARCHAR(10) NOT NULL,
            direction VARCHAR(4) NOT NULL,
            volume DOUBLE PRECISION NOT NULL,
            price DOUBLE PRECISION NOT NULL,
            sl DOUBLE PRECISION,
            tp DOUBLE PRECISION,
            timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (id, timestamp)
        ) PARTITION BY RANGE (timestamp)
    """)

    # Step 3: Create default partition for existing and unmapped data
    op.execute("""
        CREATE TABLE trade_events_default PARTITION OF trade_events DEFAULT
    """)

    # Step 4: Create partitions for current and next 30 days
    op.execute("""
        DO $$
        DECLARE
            d DATE;
        BEGIN
            FOR d IN SELECT generate_series(CURRENT_DATE, CURRENT_DATE + INTERVAL '30 days', '1 day')::date
            LOOP
                EXECUTE format(
                    'CREATE TABLE trade_events_%s PARTITION OF trade_events FOR VALUES FROM (%L) TO (%L)',
                    to_char(d, 'YYYY_MM_DD'),
                    d,
                    d + INTERVAL '1 day'
                );
            END LOOP;
        END $$;
    """)

    # Step 5: Migrate existing data
    op.execute("INSERT INTO trade_events SELECT * FROM trade_events_old")

    # Step 6: Recreate indexes
    op.execute("CREATE INDEX ix_trade_events_master ON trade_events (master_account_id)")
    op.execute("CREATE INDEX ix_trade_events_ts ON trade_events (timestamp)")

    # Step 7: Drop old table
    op.execute("DROP TABLE trade_events_old CASCADE")

    # Similarly partition trade_copies by executed_at
    op.execute("ALTER TABLE trade_copies RENAME TO trade_copies_old")
    op.execute("""
        CREATE TABLE trade_copies (
            id UUID NOT NULL,
            trade_event_id UUID NOT NULL,
            mt5_account_id UUID NOT NULL REFERENCES mt5_accounts(id),
            client_ticket BIGINT,
            volume DOUBLE PRECISION NOT NULL,
            price DOUBLE PRECISION,
            status VARCHAR(10) DEFAULT 'pending',
            error_message VARCHAR(500),
            latency_ms INTEGER,
            executed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (id, executed_at)
        ) PARTITION BY RANGE (executed_at)
    """)
    op.execute("CREATE TABLE trade_copies_default PARTITION OF trade_copies DEFAULT")
    op.execute("""
        DO $$
        DECLARE
            d DATE;
        BEGIN
            FOR d IN SELECT generate_series(CURRENT_DATE, CURRENT_DATE + INTERVAL '30 days', '1 day')::date
            LOOP
                EXECUTE format(
                    'CREATE TABLE trade_copies_%s PARTITION OF trade_copies FOR VALUES FROM (%L) TO (%L)',
                    to_char(d, 'YYYY_MM_DD'),
                    d,
                    d + INTERVAL '1 day'
                );
            END LOOP;
        END $$;
    """)
    op.execute("INSERT INTO trade_copies SELECT * FROM trade_copies_old")
    op.execute("CREATE INDEX ix_trade_copies_event ON trade_copies (trade_event_id)")
    op.execute("CREATE INDEX ix_trade_copies_account ON trade_copies (mt5_account_id)")
    op.execute("CREATE INDEX ix_trade_copies_ts ON trade_copies (executed_at)")
    op.execute("DROP TABLE trade_copies_old")


def downgrade() -> None:
    # Revert to non-partitioned tables
    op.execute("ALTER TABLE trade_events RENAME TO trade_events_partitioned")
    op.execute("""
        CREATE TABLE trade_events AS SELECT * FROM trade_events_partitioned
    """)
    op.execute("DROP TABLE trade_events_partitioned CASCADE")

    op.execute("ALTER TABLE trade_copies RENAME TO trade_copies_partitioned")
    op.execute("""
        CREATE TABLE trade_copies AS SELECT * FROM trade_copies_partitioned
    """)
    op.execute("DROP TABLE trade_copies_partitioned CASCADE")
