"""V2 pool-based engine — base tables.

Revision ID: 015
Revises: 014

Creates the V2 schema in strict isolation from V1:
  - pool_terminal           : segmented pools (master_id, strategy_id)
  - account_terminal_map    : account → pool/terminal binding
  - v2_orders               : orders executed by V2 engine

All V2 tables are prefixed (`v2_` or `pool_`) and never overlap with V1.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade():
    # ── pool_terminal ─────────────────────────────────────────────
    op.create_table(
        "pool_terminal",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("pool_name", sa.String(64), nullable=False),
        sa.Column("master_id", UUID(as_uuid=True),
                  sa.ForeignKey("master_accounts.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("strategy_id", UUID(as_uuid=True),
                  sa.ForeignKey("strategies.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("terminal_path", sa.Text, nullable=False),
        sa.Column("capacity", sa.Integer, nullable=False, server_default="15"),
        sa.Column("current_load", sa.Integer, nullable=False, server_default="0"),
        # ACTIVE | STANDBY | DRAINING | OFFLINE
        sa.Column("status", sa.String(16), nullable=False, server_default="STANDBY"),
        sa.Column("host", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("pool_name", name="uq_pool_terminal_name"),
        sa.CheckConstraint("current_load >= 0", name="ck_pool_load_nonneg"),
        sa.CheckConstraint("capacity > 0", name="ck_pool_capacity_pos"),
        sa.CheckConstraint(
            "status IN ('ACTIVE','STANDBY','DRAINING','OFFLINE')",
            name="ck_pool_status",
        ),
    )
    op.create_index(
        "ix_pool_terminal_strategy_status",
        "pool_terminal",
        ["strategy_id", "status"],
    )
    op.create_index(
        "ix_pool_terminal_master",
        "pool_terminal",
        ["master_id"],
    )

    # ── account_terminal_map ──────────────────────────────────────
    op.create_table(
        "account_terminal_map",
        sa.Column("account_id", UUID(as_uuid=True),
                  sa.ForeignKey("mt5_accounts.id", ondelete="CASCADE"),
                  primary_key=True),
        sa.Column("pool_id", UUID(as_uuid=True),
                  sa.ForeignKey("pool_terminal.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("terminal_id", UUID(as_uuid=True),
                  sa.ForeignKey("pool_terminal.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("master_id", UUID(as_uuid=True),
                  sa.ForeignKey("master_accounts.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("strategy_id", UUID(as_uuid=True),
                  sa.ForeignKey("strategies.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("engine_version", sa.String(8), nullable=False,
                  server_default="v2"),
        sa.Column("assigned_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_account_terminal_map_pool",
        "account_terminal_map",
        ["pool_id"],
    )
    op.create_index(
        "ix_account_terminal_map_strategy",
        "account_terminal_map",
        ["strategy_id"],
    )

    # ── v2_orders ─────────────────────────────────────────────────
    op.create_table(
        "v2_orders",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("account_id", UUID(as_uuid=True),
                  sa.ForeignKey("mt5_accounts.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("master_id", UUID(as_uuid=True),
                  sa.ForeignKey("master_accounts.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("strategy_id", UUID(as_uuid=True),
                  sa.ForeignKey("strategies.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("pool_id", UUID(as_uuid=True),
                  sa.ForeignKey("pool_terminal.id", ondelete="RESTRICT"),
                  nullable=True),
        sa.Column("master_ticket", sa.BigInteger, nullable=False),
        sa.Column("client_ticket", sa.BigInteger, nullable=True),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("magic", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("comment", sa.String(64), nullable=True),
        sa.Column("action", sa.String(16), nullable=False),  # OPEN/CLOSE/MODIFY
        sa.Column("side", sa.String(8), nullable=True),       # BUY/SELL
        sa.Column("volume", sa.Numeric(18, 4), nullable=True),
        sa.Column("open_price", sa.Numeric(18, 6), nullable=True),
        sa.Column("close_price", sa.Numeric(18, 6), nullable=True),
        sa.Column("retcode", sa.Integer, nullable=True),
        sa.Column("status", sa.String(24), nullable=False, server_default="PENDING"),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index(
        "ix_v2_orders_account_open",
        "v2_orders",
        ["account_id"],
        postgresql_where=sa.text("closed_at IS NULL"),
    )
    op.create_index(
        "ix_v2_orders_master_ticket",
        "v2_orders",
        ["master_id", "master_ticket"],
    )
    op.create_index(
        "ix_v2_orders_client_ticket",
        "v2_orders",
        ["account_id", "client_ticket"],
    )


def downgrade():
    op.drop_index("ix_v2_orders_client_ticket", table_name="v2_orders")
    op.drop_index("ix_v2_orders_master_ticket", table_name="v2_orders")
    op.drop_index("ix_v2_orders_account_open", table_name="v2_orders")
    op.drop_table("v2_orders")

    op.drop_index("ix_account_terminal_map_strategy", table_name="account_terminal_map")
    op.drop_index("ix_account_terminal_map_pool", table_name="account_terminal_map")
    op.drop_table("account_terminal_map")

    op.drop_index("ix_pool_terminal_master", table_name="pool_terminal")
    op.drop_index("ix_pool_terminal_strategy_status", table_name="pool_terminal")
    op.drop_table("pool_terminal")
