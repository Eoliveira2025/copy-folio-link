"""Add affiliate system tables.

Revision ID: 024
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "024"
down_revision = "023"
branch_labels = None
depends_on = None

def upgrade():
    # Create affiliates table
    op.create_table(
        "affiliates",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("commission_percentage", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("commission_base", sa.Enum("COMPANY_COMMISSION", "GROSS_PROFIT", name="commissionbase"), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("must_change_password", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id")
    )
    op.create_index(op.f("ix_affiliates_email"), "affiliates", ["email"], unique=True)

    # Create affiliate_referrals table
    op.create_table(
        "affiliate_referrals",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("affiliate_id", sa.UUID(), nullable=False),
        sa.Column("referred_user_id", sa.UUID(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["affiliate_id"], ["affiliates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ),
        sa.ForeignKeyConstraint(["referred_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("referred_user_id")
    )
    op.create_index(op.f("ix_affiliate_referrals_affiliate_id"), "affiliate_referrals", ["affiliate_id"], unique=False)

    # Create affiliate_commissions table
    op.create_table(
        "affiliate_commissions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("affiliate_id", sa.UUID(), nullable=False),
        sa.Column("referred_user_id", sa.UUID(), nullable=False),
        sa.Column("performance_cycle_id", sa.UUID(), nullable=True),
        sa.Column("gross_profit", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("company_commission_amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("affiliate_percentage", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("commission_base", sa.Enum("COMPANY_COMMISSION", "GROSS_PROFIT", name="commissionbase"), nullable=False),
        sa.Column("affiliate_commission_amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("status", sa.Enum("PENDING", "APPROVED", "PAID", "CANCELLED", name="commissionstatus"), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["affiliate_id"], ["affiliates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["performance_cycle_id"], ["performance_billing_cycles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["referred_user_id"], ["users.id"], ),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index(op.f("ix_affiliate_commissions_affiliate_id"), "affiliate_commissions", ["affiliate_id"], unique=False)

def downgrade():
    op.drop_index(op.f("ix_affiliate_commissions_affiliate_id"), table_name="affiliate_commissions")
    op.drop_table("affiliate_commissions")
    op.drop_index(op.f("ix_affiliate_referrals_affiliate_id"), table_name="affiliate_referrals")
    op.drop_table("affiliate_referrals")
    op.drop_index(op.f("ix_affiliates_email"), table_name="affiliates")
    op.drop_table("affiliates")
    # Note: Enums are not dropped here to avoid issues if shared, 
    # but in a clean migration they should be handled.
