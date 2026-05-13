"""V2 strategy change requests + V2-only flag tables.

Revision ID: 016
Revises: 015

Tables added (V2-only, never touch V1):
  v2_master_flags          : marks masters as engine_version='v2'
  v2_account_flags         : marks client accounts as engine_version='v2'
  v2_strategy_change_requests : workflow for strategy changes
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade():
    # ── v2_master_flags ──────────────────────────────────────────
    op.create_table(
        "v2_master_flags",
        sa.Column("master_id", UUID(as_uuid=True),
                  sa.ForeignKey("master_accounts.id", ondelete="CASCADE"),
                  primary_key=True),
        sa.Column("engine_version", sa.String(8), nullable=False,
                  server_default="v2"),
        sa.Column("enabled", sa.Boolean, nullable=False,
                  server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )

    # ── v2_account_flags ─────────────────────────────────────────
    op.create_table(
        "v2_account_flags",
        sa.Column("account_id", UUID(as_uuid=True),
                  sa.ForeignKey("mt5_accounts.id", ondelete="CASCADE"),
                  primary_key=True),
        sa.Column("engine_version", sa.String(8), nullable=False,
                  server_default="v2"),
        sa.Column("enabled", sa.Boolean, nullable=False,
                  server_default=sa.text("false")),
        sa.Column("state", sa.String(32), nullable=False,
                  server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "state IN ('ACTIVE','PENDING_STRATEGY_CHANGE','EXIT_ONLY',"
            "'READY_TO_SWITCH','SWITCHED','FAILED')",
            name="ck_v2_account_flags_state",
        ),
    )

    # ── v2_strategy_change_requests ──────────────────────────────
    op.create_table(
        "v2_strategy_change_requests",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("account_id", UUID(as_uuid=True),
                  sa.ForeignKey("mt5_accounts.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("old_strategy_id", UUID(as_uuid=True),
                  sa.ForeignKey("strategies.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("new_strategy_id", UUID(as_uuid=True),
                  sa.ForeignKey("strategies.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("old_pool_id", UUID(as_uuid=True),
                  sa.ForeignKey("pool_terminal.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("new_pool_id", UUID(as_uuid=True),
                  sa.ForeignKey("pool_terminal.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("mode", sa.String(32), nullable=False,
                  server_default="SAFE_DRAIN"),
        sa.Column("floating_pnl", sa.Numeric(18, 2), nullable=True),
        sa.Column("requested_by", UUID(as_uuid=True), nullable=True),
        sa.Column("approved_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "state IN ('PENDING_STRATEGY_CHANGE','EXIT_ONLY',"
            "'READY_TO_SWITCH','SWITCHED','FAILED')",
            name="ck_v2_change_state",
        ),
        sa.CheckConstraint(
            "mode IN ('SAFE_DRAIN','FORCE_CLOSE_AND_SWITCH')",
            name="ck_v2_change_mode",
        ),
    )
    op.create_index(
        "ix_v2_change_account_state",
        "v2_strategy_change_requests",
        ["account_id", "state"],
    )


def downgrade():
    op.drop_index("ix_v2_change_account_state",
                  table_name="v2_strategy_change_requests")
    op.drop_table("v2_strategy_change_requests")
    op.drop_table("v2_account_flags")
    op.drop_table("v2_master_flags")
