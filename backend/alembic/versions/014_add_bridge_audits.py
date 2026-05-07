"""Add bridge_audits table.

Revision ID: 014
Revises: 013
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "bridge_audits",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("bridge_execution_order_id", UUID(as_uuid=True), nullable=False),
        sa.Column("bridge_signal_id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("mt5_account_id", UUID(as_uuid=True), nullable=False),
        sa.Column("client_login", sa.String(64), nullable=False),
        sa.Column("expected_action", sa.String(16), nullable=False),
        sa.Column("expected_symbol", sa.String(32), nullable=False),
        sa.Column("expected_order_type", sa.String(32), nullable=True),
        sa.Column("expected_lot", sa.Numeric(18, 4), nullable=True),
        sa.Column("expected_sl", sa.Numeric(18, 6), nullable=True),
        sa.Column("expected_tp", sa.Numeric(18, 6), nullable=True),
        sa.Column("master_ticket", sa.String(64), nullable=True),
        sa.Column("audit_status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("detected_status", sa.String(32), nullable=True),
        sa.Column("failure_reason", sa.Text, nullable=True),
        sa.Column("auto_fix_attempted", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("auto_fix_result", JSONB, nullable=True),
        sa.Column("raw_check_payload", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_bridge_audits_status", "bridge_audits", ["audit_status"])
    op.create_index("ix_bridge_audits_eo", "bridge_audits", ["bridge_execution_order_id"])
    op.create_index("ix_bridge_audits_signal", "bridge_audits", ["bridge_signal_id"])
    op.create_index("ix_bridge_audits_login", "bridge_audits", ["client_login"])
    op.create_index("ix_bridge_audits_master_ticket", "bridge_audits", ["master_ticket"])


def downgrade():
    for ix in ("ix_bridge_audits_master_ticket", "ix_bridge_audits_login",
               "ix_bridge_audits_signal", "ix_bridge_audits_eo", "ix_bridge_audits_status"):
        op.drop_index(ix, table_name="bridge_audits")
    op.drop_table("bridge_audits")
