"""Add admin_notes, manual_payment, manual_payment_by, cancelled_at, extended_due_date to invoices.

Revision ID: 010
Revises: 009
"""
from alembic import op
import sqlalchemy as sa


revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("invoices", sa.Column("admin_notes", sa.Text(), nullable=True))
    op.add_column("invoices", sa.Column("manual_payment", sa.Boolean(), server_default="false", nullable=True))
    op.add_column("invoices", sa.Column("manual_payment_by", sa.String(length=255), nullable=True))
    op.add_column("invoices", sa.Column("manual_payment_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("invoices", sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("invoices", sa.Column("cancelled_by", sa.String(length=255), nullable=True))
    op.add_column("invoices", sa.Column("original_due_date", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("invoices", "original_due_date")
    op.drop_column("invoices", "cancelled_by")
    op.drop_column("invoices", "cancelled_at")
    op.drop_column("invoices", "manual_payment_at")
    op.drop_column("invoices", "manual_payment_by")
    op.drop_column("invoices", "manual_payment")
    op.drop_column("invoices", "admin_notes")
