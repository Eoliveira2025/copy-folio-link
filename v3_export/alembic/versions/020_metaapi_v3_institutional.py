"""Update MetaApi and CopyFactory for institutional V3.

Revision ID: 020_metaapi_v3_institutional
Revises: 019_add_metaapi_v3
Create Date: 2026-05-15 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '020_metaapi_v3_institutional'
down_revision = '019_add_metaapi_v3'
branch_labels = None
depends_on = None

def upgrade():
    # 1. Update metaapi_accounts
    # Add metrics and sync fields if they don't exist
    op.add_column('metaapi_accounts', sa.Column('account_type', sa.String(20), server_default='CLIENT'))
    op.add_column('metaapi_accounts', sa.Column('name', sa.String(100), server_default='Account'))
    op.add_column('metaapi_accounts', sa.Column('last_balance', sa.Float(), server_default='0.0'))
    op.add_column('metaapi_accounts', sa.Column('last_equity', sa.Float(), server_default='0.0'))
    op.add_column('metaapi_accounts', sa.Column('last_margin', sa.Float(), server_default='0.0'))
    op.add_column('metaapi_accounts', sa.Column('last_free_margin', sa.Float(), server_default='0.0'))
    op.add_column('metaapi_accounts', sa.Column('last_profit_loss', sa.Float(), server_default='0.0'))
    op.add_column('metaapi_accounts', sa.Column('last_positions_count', sa.Integer(), server_default='0'))
    op.add_column('metaapi_accounts', sa.Column('last_positions_json', postgresql.JSONB))
    
    # Make user_id nullable for system masters
    op.alter_column('metaapi_accounts', 'user_id', existing_type=postgresql.UUID(as_uuid=True), nullable=True)

    # 2. Create copyfactory_strategies
    op.create_table(
        'copyfactory_strategies',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('strategy_code', sa.String(50), unique=True, nullable=False),
        sa.Column('display_name', sa.String(100), nullable=False),
        sa.Column('master_account_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('metaapi_accounts.id', ondelete='SET NULL')),
        sa.Column('copyfactory_strategy_id', sa.String(100), unique=True),
        sa.Column('min_balance', sa.Float(), server_default='0.0'),
        sa.Column('risk_multiplier_default', sa.Float(), server_default='1.0'),
        sa.Column('copy_sl', sa.Boolean(), server_default='true'),
        sa.Column('copy_tp', sa.Boolean(), server_default='true'),
        sa.Column('open_small_trades', sa.Boolean(), server_default='true'),
        sa.Column('do_not_scale', sa.Boolean(), server_default='false'),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )

    # 3. Update copyfactory_subscriptions (re-create to match desired schema)
    # We drop and recreate because the old one was quite different and this is V3 early stages
    op.drop_table('copyfactory_subscriptions')
    op.create_table(
        'copyfactory_subscriptions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('client_account_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('metaapi_accounts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('strategy_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('copyfactory_strategies.id', ondelete='CASCADE'), nullable=False),
        sa.Column('copyfactory_subscription_id', sa.String(100), unique=True),
        sa.Column('status', sa.String(50), server_default='PENDING'),
        sa.Column('risk_ratio', sa.Float(), server_default='1.0'),
        sa.Column('last_error', sa.Text()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )
    op.create_index('ix_copyfactory_subscriptions_user_id', 'copyfactory_subscriptions', ['user_id'])

    # 4. Create strategy_switch_requests
    op.create_table(
        'strategy_switch_requests',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('current_strategy_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('copyfactory_strategies.id', ondelete='SET NULL')),
        sa.Column('target_strategy_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('copyfactory_strategies.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', sa.String(50), server_default='REQUESTED'),
        sa.Column('has_open_positions_at_request', sa.Boolean(), server_default='false'),
        sa.Column('open_positions_snapshot', postgresql.JSONB),
        sa.Column('requested_by', sa.String(50), server_default='user'),
        sa.Column('forced_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('notes', sa.Text()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('switched_at', sa.DateTime(timezone=True))
    )
    op.create_index('ix_strategy_switch_requests_user_id', 'strategy_switch_requests', ['user_id'])

    # 5. Create metaapi_account_metrics
    op.create_table(
        'metaapi_account_metrics',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('account_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('metaapi_accounts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('balance', sa.Float(), server_default='0.0'),
        sa.Column('equity', sa.Float(), server_default='0.0'),
        sa.Column('margin', sa.Float(), server_default='0.0'),
        sa.Column('free_margin', sa.Float(), server_default='0.0'),
        sa.Column('profit_loss', sa.Float(), server_default='0.0'),
        sa.Column('positions_count', sa.Integer(), server_default='0'),
        sa.Column('positions_json', postgresql.JSONB),
        sa.Column('captured_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )
    op.create_index('ix_metaapi_account_metrics_account_id', 'metaapi_account_metrics', ['account_id'])

    # Clean up old metaapi_masters if exists
    op.drop_table('metaapi_masters')

def downgrade():
    op.drop_table('metaapi_account_metrics')
    op.drop_table('strategy_switch_requests')
    op.drop_table('copyfactory_subscriptions')
    op.drop_table('copyfactory_strategies')
    # Re-create old tables if necessary for full rollback, but here we'll just drop added columns
    op.drop_column('metaapi_accounts', 'last_positions_json')
    op.drop_column('metaapi_accounts', 'last_positions_count')
    op.drop_column('metaapi_accounts', 'last_profit_loss')
    op.drop_column('metaapi_accounts', 'last_free_margin')
    op.drop_column('metaapi_accounts', 'last_margin')
    op.drop_column('metaapi_accounts', 'last_equity')
    op.drop_column('metaapi_accounts', 'last_balance')
    op.drop_column('metaapi_accounts', 'name')
    op.drop_column('metaapi_accounts', 'account_type')
