"""Add copy recovery infrastructure: trade_copy_recoveries table + summary columns on trade_copies.

Revision ID: 011
Revises: 010

Scope (additive, non-breaking):
    - trade_copies: add retry_attempts, recovery_type, final_status, mt5_retcode,
      mt5_retcode_comment, original_price, last_seen_price (all nullable / defaulted)
    - trade_copy_recoveries (new): one row per recovery attempt with full audit trail
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade():
    # ── Summary columns on trade_copies ──
    op.add_column("trade_copies", sa.Column("retry_attempts", sa.Integer(), server_default="0", nullable=True))
    op.add_column("trade_copies", sa.Column("recovery_type", sa.String(length=32), nullable=True))
    op.add_column("trade_copies", sa.Column("final_status", sa.String(length=64), nullable=True))
    op.add_column("trade_copies", sa.Column("mt5_retcode", sa.Integer(), nullable=True))
    op.add_column("trade_copies", sa.Column("mt5_retcode_comment", sa.String(length=255), nullable=True))
    op.add_column("trade_copies", sa.Column("original_price", sa.Float(), nullable=True))
    op.add_column("trade_copies", sa.Column("last_seen_price", sa.Float(), nullable=True))

    # ── Per-attempt audit table ──
    op.create_table(
        "trade_copy_recoveries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        # link (soft — trade_copies has composite PK, so no FK enforced here)
        sa.Column("trade_copy_id", UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("order_id", sa.String(length=100), nullable=False, index=True),
        sa.Column("mt5_account_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=True, index=True),
        # event identity
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("action", sa.String(length=10), nullable=False),  # open / close / modify
        sa.Column("direction", sa.String(length=4), nullable=False),
        sa.Column("volume", sa.Float(), nullable=False),
        sa.Column("master_ticket", sa.BigInteger(), nullable=False),
        sa.Column("client_ticket", sa.BigInteger(), nullable=True),
        # recovery context
        sa.Column("recovery_type", sa.String(length=32), nullable=False),  # open_recovery / close_recovery
        sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="1"),
        # decision & outcome (standardized reason codes)
        sa.Column("decision", sa.String(length=64), nullable=False),
        sa.Column("reason_code", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False),
        # prices
        sa.Column("original_price", sa.Float(), nullable=True),
        sa.Column("current_price", sa.Float(), nullable=True),
        sa.Column("price_delta_points", sa.Float(), nullable=True),
        # MT5 raw outcome
        sa.Column("mt5_retcode", sa.Integer(), nullable=True),
        sa.Column("mt5_retcode_comment", sa.String(length=255), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        # timestamps
        sa.Column("decided_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_recovery_status", "trade_copy_recoveries", ["status"])
    op.create_index("ix_recovery_decided_at", "trade_copy_recoveries", ["decided_at"])
    op.create_index("ix_recovery_recovery_type", "trade_copy_recoveries", ["recovery_type"])


def downgrade():
    op.drop_index("ix_recovery_recovery_type", table_name="trade_copy_recoveries")
    op.drop_index("ix_recovery_decided_at", table_name="trade_copy_recoveries")
    op.drop_index("ix_recovery_status", table_name="trade_copy_recoveries")
    op.drop_table("trade_copy_recoveries")
    op.drop_column("trade_copies", "last_seen_price")
    op.drop_column("trade_copies", "original_price")
    op.drop_column("trade_copies", "mt5_retcode_comment")
    op.drop_column("trade_copies", "mt5_retcode")
    op.drop_column("trade_copies", "final_status")
    op.drop_column("trade_copies", "recovery_type")
    op.drop_column("trade_copies", "retry_attempts")
