"""Add access_status, manual_override, last_access_check, blocked_at to subscriptions.

Revision ID: 009
Revises: 008
"""
from alembic import op
import sqlalchemy as sa

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade():
    # Create enum type first
    access_status_enum = sa.Enum("active", "warning", "grace", "blocked", name="accessstatus")
    access_status_enum.create(op.get_bind(), checkfirst=True)

    op.add_column("subscriptions", sa.Column("access_status", sa.Enum("active", "warning", "grace", "blocked", name="accessstatus"), server_default="active", nullable=True))
    op.add_column("subscriptions", sa.Column("manual_override", sa.Boolean(), server_default="false", nullable=True))
    op.add_column("subscriptions", sa.Column("last_access_check", sa.DateTime(timezone=True), nullable=True))
    op.add_column("subscriptions", sa.Column("blocked_at", sa.DateTime(timezone=True), nullable=True))

    # Set default for existing rows
    op.execute("UPDATE subscriptions SET access_status = 'active' WHERE access_status IS NULL")


def downgrade():
    op.drop_column("subscriptions", "blocked_at")
    op.drop_column("subscriptions", "last_access_check")
    op.drop_column("subscriptions", "manual_override")
    op.drop_column("subscriptions", "access_status")
    sa.Enum(name="accessstatus").drop(op.get_bind(), checkfirst=True)
