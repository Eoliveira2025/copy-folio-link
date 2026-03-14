"""Add affiliate_broker_link to system_settings.

Revision ID: 005
"""
from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("system_settings", sa.Column("affiliate_broker_link", sa.String(500), nullable=True))


def downgrade():
    op.drop_column("system_settings", "affiliate_broker_link")
