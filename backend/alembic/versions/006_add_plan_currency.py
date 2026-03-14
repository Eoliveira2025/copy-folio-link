"""Add currency column to plans table.

Revision ID: 006_add_plan_currency
Revises: 005_add_affiliate_broker_link
"""
from alembic import op
import sqlalchemy as sa

revision = "006_add_plan_currency"
down_revision = "005_add_affiliate_broker_link"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("plans", sa.Column("currency", sa.String(3), nullable=False, server_default="USD"))


def downgrade() -> None:
    op.drop_column("plans", "currency")
