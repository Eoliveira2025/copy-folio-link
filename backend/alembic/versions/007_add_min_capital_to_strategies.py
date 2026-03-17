"""Add min_capital column to strategies.

Revision ID: 007
"""
from alembic import op
import sqlalchemy as sa

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("strategies", sa.Column("min_capital", sa.Numeric(10, 2), server_default="0", nullable=False))


def downgrade():
    op.drop_column("strategies", "min_capital")
