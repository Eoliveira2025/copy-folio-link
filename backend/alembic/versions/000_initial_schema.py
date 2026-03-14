"""Create all base tables for a fresh database.

Revision ID: 000
Revises: None
Create Date: 2026-03-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "000"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Enums ──────────────────────────────────────────────
    user_role = sa.Enum("user", "admin", name="userrole", create_type=True)
    subscription_status = sa.Enum("trial", "active", "expired", "blocked", name="subscriptionstatus", create_type=True)
    invoice_status = sa.Enum("pending", "paid", "overdue", "cancelled", name="invoicestatus", create_type=True)
    payment_provider = sa.Enum("stripe", "asaas", "mercadopago", "celcoin", name="paymentprovider", create_type=True)
    strategy_level = sa.Enum("low", "medium", "high", "pro", "expert", "expert_pro", name="strategylevel", create_type=True)
    mt5_status = sa.Enum("connected", "disconnected", "blocked", name="mt5status", create_type=True)
    trade_action = sa.Enum("open", "close", "modify", name="tradeaction", create_type=True)
    copy_status = sa.Enum("pending", "executed", "failed", "skipped", name="copystatus", create_type=True)
    upgrade_status = sa.Enum("pending", "approved", "rejected", name="upgraderequestStatus", create_type=True)

    # ── users ──────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(255), unique=True, index=True, nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255)),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # ── user_roles ─────────────────────────────────────────
    op.create_table(
        "user_roles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("role", user_role, server_default="user", nullable=False),
    )

    # ── plans ──────────────────────────────────────────────
    op.create_table(
        "plans",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(100), unique=True, nullable=False),
        sa.Column("price", sa.Float, nullable=False),
        sa.Column("allowed_strategies", sa.JSON, server_default="[]"),
        sa.Column("trial_days", sa.Integer, server_default="30"),
        sa.Column("max_accounts", sa.Integer, server_default="1"),
        sa.Column("active", sa.Boolean, server_default="true"),
    )

    # ── subscriptions ──────────────────────────────────────
    op.create_table(
        "subscriptions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("plan_id", UUID(as_uuid=True), sa.ForeignKey("plans.id"), index=True),
        sa.Column("status", subscription_status, server_default="trial"),
        sa.Column("trial_start", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("trial_end", sa.DateTime(timezone=True)),
        sa.Column("current_period_start", sa.DateTime(timezone=True)),
        sa.Column("current_period_end", sa.DateTime(timezone=True)),
        sa.Column("auto_renew", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # ── invoices ───────────────────────────────────────────
    op.create_table(
        "invoices",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("subscription_id", UUID(as_uuid=True), sa.ForeignKey("subscriptions.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("amount", sa.Float, nullable=False),
        sa.Column("currency", sa.String(3), server_default="'USD'"),
        sa.Column("status", invoice_status, server_default="pending"),
        sa.Column("issue_date", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True)),
        sa.Column("external_id", sa.String(255)),
        sa.Column("provider", payment_provider),
    )

    # ── payments ───────────────────────────────────────────
    op.create_table(
        "payments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("invoice_id", UUID(as_uuid=True), sa.ForeignKey("invoices.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("provider", payment_provider, nullable=False),
        sa.Column("provider_payment_id", sa.String(255), nullable=False),
        sa.Column("amount", sa.Float, nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("raw_webhook", sa.String(5000)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # ── strategies ─────────────────────────────────────────
    op.create_table(
        "strategies",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("level", strategy_level, unique=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(500)),
        sa.Column("risk_multiplier", sa.Float, server_default="1.0"),
        sa.Column("requires_unlock", sa.Boolean, server_default="false"),
    )

    # ── master_accounts ────────────────────────────────────
    op.create_table(
        "master_accounts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("strategy_id", UUID(as_uuid=True), sa.ForeignKey("strategies.id"), unique=True, nullable=False),
        sa.Column("account_name", sa.String(255), nullable=False),
        sa.Column("login", sa.Integer, unique=True, nullable=False),
        sa.Column("server", sa.String(255), nullable=False),
        sa.Column("balance", sa.Float, server_default="0.0"),
    )

    # ── user_strategies ────────────────────────────────────
    op.create_table(
        "user_strategies",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("strategy_id", UUID(as_uuid=True), sa.ForeignKey("strategies.id"), nullable=False),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("unlocked_by_admin", sa.Boolean, server_default="false"),
        sa.Column("activated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # ── mt5_accounts ───────────────────────────────────────
    op.create_table(
        "mt5_accounts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("login", sa.Integer, unique=True, nullable=False),
        sa.Column("encrypted_password", sa.String(512), nullable=False),
        sa.Column("server", sa.String(255), nullable=False),
        sa.Column("status", mt5_status, server_default="disconnected"),
        sa.Column("balance", sa.Float),
        sa.Column("equity", sa.Float),
        sa.Column("last_connected_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # ── trade_events ───────────────────────────────────────
    op.create_table(
        "trade_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("master_account_id", UUID(as_uuid=True), sa.ForeignKey("master_accounts.id"), index=True, nullable=False),
        sa.Column("ticket", sa.BigInteger, nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("action", trade_action, nullable=False),
        sa.Column("direction", sa.String(4), nullable=False),
        sa.Column("volume", sa.Float, nullable=False),
        sa.Column("price", sa.Float, nullable=False),
        sa.Column("sl", sa.Float),
        sa.Column("tp", sa.Float),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # ── trade_copies ───────────────────────────────────────
    op.create_table(
        "trade_copies",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("trade_event_id", UUID(as_uuid=True), sa.ForeignKey("trade_events.id"), index=True, nullable=False),
        sa.Column("mt5_account_id", UUID(as_uuid=True), sa.ForeignKey("mt5_accounts.id"), index=True, nullable=False),
        sa.Column("client_ticket", sa.BigInteger),
        sa.Column("volume", sa.Float, nullable=False),
        sa.Column("price", sa.Float),
        sa.Column("status", copy_status, server_default="pending"),
        sa.Column("error_message", sa.String(500)),
        sa.Column("latency_ms", sa.Integer),
        sa.Column("executed_at", sa.DateTime(timezone=True)),
    )

    # ── terms_documents ────────────────────────────────────
    op.create_table(
        "terms_documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("company_name", sa.String(255), nullable=False, server_default="'CopyTrade Pro'"),
        sa.Column("language", sa.String(10), nullable=False, server_default="'en'"),
        sa.Column("is_active", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # ── terms_acceptances ──────────────────────────────────
    op.create_table(
        "terms_acceptances",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("terms_id", UUID(as_uuid=True), sa.ForeignKey("terms_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("ip_address", sa.String(45)),
        sa.Column("user_agent", sa.String(500)),
    )

    # ── upgrade_requests ───────────────────────────────────
    op.create_table(
        "upgrade_requests",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("current_plan_id", UUID(as_uuid=True), sa.ForeignKey("plans.id")),
        sa.Column("target_plan_id", UUID(as_uuid=True), sa.ForeignKey("plans.id"), nullable=False),
        sa.Column("mt5_balance", sa.Float, nullable=False),
        sa.Column("status", upgrade_status, server_default="pending"),
        sa.Column("admin_note", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_table("upgrade_requests")
    op.drop_table("terms_acceptances")
    op.drop_table("terms_documents")
    op.drop_table("trade_copies")
    op.drop_table("trade_events")
    op.drop_table("mt5_accounts")
    op.drop_table("user_strategies")
    op.drop_table("master_accounts")
    op.drop_table("strategies")
    op.drop_table("payments")
    op.drop_table("invoices")
    op.drop_table("subscriptions")
    op.drop_table("plans")
    op.drop_table("user_roles")
    op.drop_table("users")

    # Drop enums
    for name in [
        "upgraderequestStatus", "copystatus", "tradeaction", "mt5status",
        "strategylevel", "paymentprovider", "invoicestatus",
        "subscriptionstatus", "userrole",
    ]:
        op.execute(f"DROP TYPE IF EXISTS {name}")
