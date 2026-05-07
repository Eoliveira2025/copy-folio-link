"""Add bridge_signals + bridge_execution_orders tables.

Revision ID: 013
Revises: 012
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "bridge_signals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("master_id", sa.String(128), nullable=False, index=True),
        sa.Column("strategy_id", sa.String(64), nullable=True, index=True),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("master_ticket", sa.String(64), nullable=True),
        sa.Column("position_id", sa.String(64), nullable=True),
        sa.Column("order_type", sa.String(32), nullable=True),
        sa.Column("volume", sa.Numeric(18, 4), nullable=False),
        sa.Column("price", sa.Numeric(18, 6), nullable=True),
        sa.Column("sl", sa.Numeric(18, 6), nullable=True),
        sa.Column("tp", sa.Numeric(18, 6), nullable=True),
        sa.Column("master_balance", sa.Numeric(18, 2), nullable=True),
        sa.Column("raw_payload", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.String(32), nullable=False, server_default="received"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_bridge_signals_master_ticket", "bridge_signals", ["master_ticket"])
    op.create_index("ix_bridge_signals_status", "bridge_signals", ["status"])

    op.create_table(
        "bridge_execution_orders",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("bridge_signal_id", UUID(as_uuid=True),
                  sa.ForeignKey("bridge_signals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("mt5_account_id", UUID(as_uuid=True), nullable=False),
        sa.Column("client_login", sa.String(64), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("order_type", sa.String(32), nullable=True),
        sa.Column("calculated_lot", sa.Numeric(18, 4), nullable=False),
        sa.Column("price", sa.Numeric(18, 6), nullable=True),
        sa.Column("sl", sa.Numeric(18, 6), nullable=True),
        sa.Column("tp", sa.Numeric(18, 6), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("redis_queue", sa.String(128), nullable=False),
        sa.Column("result_payload", JSONB, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("bridge_signal_id", "mt5_account_id", "action",
                            name="uq_bridge_exec_signal_account_action"),
    )
    op.create_index("ix_bridge_exec_user", "bridge_execution_orders", ["user_id"])
    op.create_index("ix_bridge_exec_account", "bridge_execution_orders", ["mt5_account_id"])
    op.create_index("ix_bridge_exec_login", "bridge_execution_orders", ["client_login"])
    op.create_index("ix_bridge_exec_status", "bridge_execution_orders", ["status"])
    op.create_index("ix_bridge_exec_signal", "bridge_execution_orders", ["bridge_signal_id"])


def downgrade():
    op.drop_index("ix_bridge_exec_signal", table_name="bridge_execution_orders")
    op.drop_index("ix_bridge_exec_status", table_name="bridge_execution_orders")
    op.drop_index("ix_bridge_exec_login", table_name="bridge_execution_orders")
    op.drop_index("ix_bridge_exec_account", table_name="bridge_execution_orders")
    op.drop_index("ix_bridge_exec_user", table_name="bridge_execution_orders")
    op.drop_table("bridge_execution_orders")
    op.drop_index("ix_bridge_signals_status", table_name="bridge_signals")
    op.drop_index("ix_bridge_signals_master_ticket", table_name="bridge_signals")
    op.drop_table("bridge_signals")
