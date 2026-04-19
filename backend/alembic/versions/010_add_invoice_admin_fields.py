"""Add minimal admin fields to invoices: admin_notes, manual_payment, manual_payment_by, original_due_date.

Revision ID: 010
Revises: 009

Scope (incremental & safe):
    - admin_notes: free-form internal notes (timestamped lines appended by admin actions)
    - manual_payment: flag indicating settlement was performed manually (not via gateway/webhook)
    - manual_payment_by: identifier (email) of the admin who manually settled
    - original_due_date: preserves the first due_date when admin extends it (UI clarity)

Intentionally NOT added in this phase:
    - manual_payment_at, cancelled_at, cancelled_by, dedicated audit/event tables
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
    op.add_column("invoices", sa.Column("original_due_date", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("invoices", "original_due_date")
    op.drop_column("invoices", "manual_payment_by")
    op.drop_column("invoices", "manual_payment")
    op.drop_column("invoices", "admin_notes")
