"""Add MetaApi V3 Institutional Monitoring.

Revision ID: 022_add_metaapi_monitoring
Revises: 021_add_metaapi_reconciliation
Create Date: 2026-05-17 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '022_add_metaapi_monitoring'
down_revision = '021_add_metaapi_reconciliation'
branch_labels = None
depends_on = None

def upgrade():
    # Create metaapi_monitor_events
    op.create_table(
        'metaapi_monitor_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('metaapi_account_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('metaapi_accounts.id', ondelete='CASCADE'), nullable=True),
        sa.Column('severity', sa.String(20), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )
    op.create_index('ix_metaapi_monitor_events_account_id', 'metaapi_monitor_events', ['metaapi_account_id'])
    op.create_index('ix_metaapi_monitor_events_severity', 'metaapi_monitor_events', ['severity'])
    op.create_index('ix_metaapi_monitor_events_created_at', 'metaapi_monitor_events', ['created_at'])

def downgrade():
    op.drop_table('metaapi_monitor_events')
