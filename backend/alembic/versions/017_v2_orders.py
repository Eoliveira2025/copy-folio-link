"""V2 order persistence.

Revision ID: 017
Revises: 016

Adds v2_orders table to track master -> client ticket relationships.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "v2_orders",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("account_id", UUID(as_uuid=True),
                  sa.ForeignKey("mt5_accounts.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("pool_id", UUID(as_uuid=True),
                  sa.ForeignKey("pool_terminal.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("master_id", UUID(as_uuid=True),
                  sa.ForeignKey("master_accounts.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("strategy_id", UUID(as_uuid=True),
                  sa.ForeignKey("strategies.id", ondelete="CASCADE"),
                  nullable=False),
        
        sa.Column("master_ticket", sa.BigInteger, nullable=False),
        sa.Column("client_ticket", sa.BigInteger, nullable=True),
        sa.Column("deal_ticket", sa.BigInteger, nullable=True),
        
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),  # OPEN, CLOSE
        sa.Column("side", sa.String(16), nullable=True),    # BUY, SELL
        sa.Column("volume", sa.Numeric(12, 2), nullable=False),
        sa.Column("price", sa.Numeric(18, 6), nullable=True),
        
        sa.Column("status", sa.String(32), nullable=False), # DONE, FAILED, PENDING
        sa.Column("retcode", sa.Integer, nullable=True),
        sa.Column("broker_comment", sa.String(255), nullable=True),
        
        sa.Column("order_latency_ms", sa.Float, nullable=True),
        sa.Column("login_latency_ms", sa.Float, nullable=True),
        
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index(
        "ix_v2_orders_lookup",
        "v2_orders",
        ["master_id", "master_ticket"],
    )
    op.create_index(
        "ix_v2_orders_client_ticket",
        "v2_orders",
        ["client_ticket"],
    )


def downgrade():
    op.drop_table("v2_orders")
