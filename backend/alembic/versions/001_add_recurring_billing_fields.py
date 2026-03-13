"""add recurring billing fields

Revision ID: 001
Revises: None
Create Date: 2026-03-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("subscriptions", sa.Column("next_billing_date", sa.DateTime(timezone=True), nullable=True))
    op.add_column("subscriptions", sa.Column("billing_cycle_days", sa.Integer(), server_default="30", nullable=False))


def downgrade() -> None:
    op.drop_column("subscriptions", "billing_cycle_days")
    op.drop_column("subscriptions", "next_billing_date")
