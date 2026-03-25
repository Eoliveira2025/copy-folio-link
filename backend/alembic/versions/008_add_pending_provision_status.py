"""Add PENDING_PROVISION status to MT5 accounts.

Revision ID: 008_add_pending_provision_status
"""
from alembic import op
import sqlalchemy as sa

revision = "008_add_pending_provision"
down_revision = "007_add_min_capital_to_strategies"
branch_labels = None
depends_on = None


def upgrade():
    # Add new enum value to mt5status
    op.execute("ALTER TYPE mt5status ADD VALUE IF NOT EXISTS 'pending_provision'")


def downgrade():
    # PostgreSQL does not support removing enum values easily
    pass
