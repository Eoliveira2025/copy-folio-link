"""add system_settings and risk_incidents tables

Revision ID: 003
Revises: 002
Create Date: 2026-03-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "system_settings",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("global_max_drawdown_percent", sa.Float(), nullable=False, server_default="50.0"),
        sa.Column("protection_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "risk_incidents",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("incident_type", sa.String(50), nullable=False),
        sa.Column("drawdown_percent", sa.Float(), nullable=False),
        sa.Column("total_balance", sa.Float(), nullable=False),
        sa.Column("total_equity", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # Insert default settings
    op.execute("""
        INSERT INTO system_settings (global_max_drawdown_percent, protection_enabled)
        VALUES (50.0, true)
    """)


def downgrade() -> None:
    op.drop_table("risk_incidents")
    op.drop_table("system_settings")
