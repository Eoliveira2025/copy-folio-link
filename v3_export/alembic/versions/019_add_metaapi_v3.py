"""Add MetaApi and CopyFactory tables for V3.

Revision ID: 019_add_metaapi_v3
Revises: 018_v2_symbol_map
Create Date: 2026-05-14 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '019_add_metaapi_v3'
down_revision = '018_v2_symbol_map'
branch_labels = None
depends_on = None

def upgrade():
    # MetaApi Accounts
    op.create_table(
        'metaapi_accounts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('login', sa.String(50), nullable=False),
        sa.Column('server', sa.String(100), nullable=False),
        sa.Column('broker', sa.String(100)),
        sa.Column('metaapi_account_id', sa.String(100), unique=True),
        sa.Column('deployment_status', sa.String(50), default='PENDING'),
        sa.Column('connection_status', sa.String(50), default='DISCONNECTED'),
        sa.Column('region', sa.String(50), default='new-york'),
        sa.Column('error_message', sa.Text),
        sa.Column('last_sync_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now())
    )
    op.create_index('ix_metaapi_accounts_user_id', 'metaapi_accounts', ['user_id'])

    # MetaApi Masters
    op.create_table(
        'metaapi_masters',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('strategy_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('strategies.id'), nullable=False),
        sa.Column('master_user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('login', sa.String(50), nullable=False),
        sa.Column('server', sa.String(100), nullable=False),
        sa.Column('metaapi_account_id', sa.String(100), unique=True),
        sa.Column('copyfactory_strategy_id', sa.String(100), unique=True),
        sa.Column('status', sa.String(50), default='ACTIVE'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now())
    )

    # CopyFactory Subscriptions
    op.create_table(
        'copyfactory_subscriptions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('strategy_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('strategies.id'), nullable=False),
        sa.Column('metaapi_account_id', sa.String(100), nullable=False),
        sa.Column('copyfactory_strategy_id', sa.String(100), nullable=False),
        sa.Column('copyfactory_subscription_id', sa.String(100), unique=True),
        sa.Column('risk_ratio', sa.Float, default=1.0),
        sa.Column('symbol_mapping', postgresql.JSONB),
        sa.Column('status', sa.String(50), default='INACTIVE'),
        sa.Column('last_sync_at', sa.DateTime(timezone=True)),
        sa.Column('error_message', sa.Text),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now())
    )

    # MetaApi Events
    op.create_table(
        'metaapi_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('type', sa.String(100), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('account_id', sa.String(100)),
        sa.Column('payload', postgresql.JSONB),
        sa.Column('status', sa.String(50)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )

def downgrade():
    op.drop_table('metaapi_events')
    op.drop_table('copyfactory_subscriptions')
    op.drop_table('metaapi_masters')
    op.drop_table('metaapi_accounts')
