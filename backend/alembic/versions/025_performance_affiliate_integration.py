"""Integrate performance billing with affiliate commissions.

Revision ID: 025
"""
from alembic import op
import sqlalchemy as sa

revision = "025"
down_revision = "024"
branch_labels = None
depends_on = None

def upgrade():
    # Add unique constraint to prevent duplicate commissions for the same performance cycle
    op.create_unique_constraint(
        "uq_affiliate_commissions_cycle", 
        "affiliate_commissions", 
        ["performance_cycle_id"]
    )

    # Add indexes for performance optimization
    op.create_index(
        "idx_affiliate_commissions_cycle_id", 
        "affiliate_commissions", 
        ["performance_cycle_id"], 
        unique=False
    )
    op.create_index(
        "idx_affiliate_referrals_referred_user_id", 
        "affiliate_referrals", 
        ["referred_user_id"], 
        unique=False
    )

def downgrade():
    op.drop_index("idx_affiliate_referrals_referred_user_id", table_name="affiliate_referrals")
    op.drop_index("idx_affiliate_commissions_cycle_id", table_name="affiliate_commissions")
    op.drop_constraint("uq_affiliate_commissions_cycle", "affiliate_commissions", type_="unique")
