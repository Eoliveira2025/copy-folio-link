"""Add password_reset_tokens and dead_letter_trades tables.

Revision ID: 004
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade():
    # Password reset tokens
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token", sa.String(255), unique=True, index=True, nullable=False),
        sa.Column("used", sa.Boolean, default=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # Dead letter trades
    op.create_table(
        "dead_letter_trades",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("order_id", sa.String(100), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("action", sa.String(10), nullable=False),
        sa.Column("direction", sa.String(4), nullable=False),
        sa.Column("volume", sa.Float, nullable=False),
        sa.Column("master_ticket", sa.BigInteger, nullable=False),
        sa.Column("client_mt5_id", sa.String(100), nullable=False),
        sa.Column("error_message", sa.Text, nullable=False),
        sa.Column("attempt_count", sa.Integer, default=1),
        sa.Column("raw_payload", sa.Text, nullable=False),
        sa.Column("status", sa.String(20), default="pending"),
        sa.Column("resolution_note", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_dead_letter_trades_status", "dead_letter_trades", ["status"])


def downgrade():
    op.drop_table("dead_letter_trades")
    op.drop_table("password_reset_tokens")
