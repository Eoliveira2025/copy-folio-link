"""Add Position Reconciliation Engine for MetaApi V3.

Revision ID: 021_add_metaapi_reconciliation
Revises: 020_metaapi_v3_institutional
Create Date: 2026-05-15 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '021_add_metaapi_reconciliation'
down_revision = '020_metaapi_v3_institutional'
branch_labels = None
depends_on = None

def upgrade():
    # 1. Create metaapi_reconciliation_settings
    op.create_table(
        'metaapi_reconciliation_settings',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('auto_close_orphan_positions', sa.Boolean(), server_default='true'),
        sa.Column('orphan_auto_close_loss_limit', sa.Float(), server_default='-2.00'),
        sa.Column('orphan_auto_close_profit_enabled', sa.Boolean(), server_default='true'),
        sa.Column('lot_tolerance', sa.Float(), server_default='0.01'),
        sa.Column('strict_symbol_match', sa.Boolean(), server_default='true'),
        sa.Column('price_tolerance_points', sa.Integer(), server_default='50'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )

    # 2. Create position_reconciliation_events
    op.create_table(
        'position_reconciliation_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('account_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('metaapi_accounts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('master_account_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('metaapi_accounts.id', ondelete='SET NULL')),
        sa.Column('subscriber_account_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('metaapi_accounts.id', ondelete='SET NULL')),
        sa.Column('symbol', sa.String(50), nullable=False),
        sa.Column('position_id', sa.String(100), nullable=False),
        sa.Column('side', sa.String(10), nullable=False),
        sa.Column('volume', sa.Float(), nullable=False),
        sa.Column('open_price', sa.Float(), nullable=False),
        sa.Column('current_price', sa.Float(), nullable=False),
        sa.Column('profit', sa.Float(), nullable=False),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('reason', sa.Text()),
        sa.Column('snapshot_master_positions', postgresql.JSONB),
        sa.Column('snapshot_subscriber_positions', postgresql.JSONB),
        sa.Column('action_taken', sa.String(100)),
        sa.Column('approved_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )
    op.create_index('ix_position_reconciliation_events_account_id', 'position_reconciliation_events', ['account_id'])
    op.create_index('ix_position_reconciliation_events_status', 'position_reconciliation_events', ['status'])

def downgrade():
    op.drop_table('position_reconciliation_events')
    op.drop_table('metaapi_reconciliation_settings')
