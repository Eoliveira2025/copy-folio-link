"""Add strategy_requests table and min_capital to strategies.

Revision ID: 007
"""
from alembic import op
import sqlalchemy as sa

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade():
    # Add min_capital to strategies
    op.add_column("strategies", sa.Column("min_capital", sa.Numeric(10, 2), server_default="0", nullable=False))

    # Create strategy_requests table
    op.create_table(
        "strategy_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("current_strategy_id", sa.Uuid(), sa.ForeignKey("strategies.id"), nullable=True),
        sa.Column("target_strategy_id", sa.Uuid(), sa.ForeignKey("strategies.id"), nullable=False),
        sa.Column("mt5_balance", sa.Float(), nullable=False),
        sa.Column("status", sa.Enum("pending", "approved", "rejected", name="strategyrequeststatustype"), nullable=False, server_default="pending"),
        sa.Column("admin_note", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_table("strategy_requests")
    op.execute("DROP TYPE IF EXISTS strategyrequeststatustype")
    op.drop_column("strategies", "min_capital")
