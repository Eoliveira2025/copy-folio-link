"""Performance billing core tables.

Revision ID: 023
Revises: 022
Create Date: 2026-05-20 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '023'
down_revision = '022'
branch_labels = None
depends_on = None

def upgrade():
    # Create billing_methods table
    op.create_table(
        'billing_methods',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('method', sa.String(length=50), nullable=False),
        sa.Column('performance_percentage', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('user_id')
    )
    op.create_index(op.f('ix_billing_methods_user_id'), 'billing_methods', ['user_id'], unique=True)

    # Create performance_billing_cycles table
    op.create_table(
        'performance_billing_cycles',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('account_source', sa.String(length=50), nullable=False),
        sa.Column('account_login', sa.String(length=50), nullable=False),
        sa.Column('strategy_code', sa.String(length=50), nullable=True),
        sa.Column('cycle_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('cycle_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('start_balance', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('end_balance', sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column('gross_profit', sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column('commission_percentage', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('commission_amount', sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('invoice_id', sa.UUID(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ondelete='SET NULL')
    )
    op.create_index(op.f('ix_performance_billing_cycles_user_id'), 'performance_billing_cycles', ['user_id'], unique=False)

def downgrade():
    op.drop_index(op.f('ix_performance_billing_cycles_user_id'), table_name='performance_billing_cycles')
    op.drop_table('performance_billing_cycles')
    op.drop_index(op.f('ix_billing_methods_user_id'), table_name='billing_methods')
    op.drop_table('billing_methods')
