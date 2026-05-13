"""add v2_symbol_map and update v2_orders

Revision ID: 018
Revises: 017
Create Date: 2026-05-13 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '018'
down_revision = '017'
branch_labels = None
depends_on = None

def upgrade():
    # 1. Create account_symbol_map table
    op.create_table(
        'account_symbol_map',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column('account_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('mt5_accounts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('raw_symbol', sa.String(50), nullable=False),
        sa.Column('broker_symbol', sa.String(50), nullable=False),
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint('account_id', 'raw_symbol', name='uq_account_raw_symbol')
    )
    op.create_index('ix_account_symbol_map_account_id', 'account_symbol_map', ['account_id'])

    # 2. Update v2_orders table with missing columns if they don't exist
    # Based on the user request, we need: price, broker_comment, order_latency_ms, login_latency_ms, deal_ticket, updated_at
    # Note: 017 might have some, but let's ensure they are there
    
    # Check existing columns first to avoid errors
    conn = op.get_bind()
    columns = [c['name'] for c in sa.inspect(conn).get_columns('v2_orders')]
    
    if 'price' not in columns:
        op.add_column('v2_orders', sa.Column('price', sa.Numeric(precision=20, scale=10)))
    if 'broker_comment' not in columns:
        op.add_column('v2_orders', sa.Column('broker_comment', sa.String(255)))
    if 'order_latency_ms' not in columns:
        op.add_column('v2_orders', sa.Column('order_latency_ms', sa.Float()))
    if 'login_latency_ms' not in columns:
        op.add_column('v2_orders', sa.Column('login_latency_ms', sa.Float()))
    if 'deal_ticket' not in columns:
        op.add_column('v2_orders', sa.Column('deal_ticket', sa.BigInteger()))
    if 'updated_at' not in columns:
        op.add_column('v2_orders', sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()))

def downgrade():
    op.drop_table('account_symbol_map')
    # No easy way to drop columns safely if they were already there, 
    # but for a downgrade we can just leave them or drop if we're sure.
