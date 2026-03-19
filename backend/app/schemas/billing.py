"""Subscription, Invoice, Checkout, and Upgrade Request schemas."""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
import uuid


class SubscriptionResponse(BaseModel):
    id: uuid.UUID
    status: str
    plan_name: str | None = None
    plan_price: float | None = None
    plan_currency: str | None = None
    trial_start: datetime
    trial_end: datetime | None
    current_period_start: datetime | None
    current_period_end: datetime | None
    next_billing_date: datetime | None = None
    auto_renew: bool

    class Config:
        from_attributes = True


class InvoiceResponse(BaseModel):
    id: uuid.UUID
    amount: float
    currency: str
    status: str
    issue_date: datetime
    due_date: datetime
    paid_at: datetime | None
    provider: str | None
    checkout_url: str | None = None

    class Config:
        from_attributes = True


class CheckoutRequest(BaseModel):
    plan_id: uuid.UUID
    billing_type: str = "PIX"  # PIX, BOLETO, CREDIT_CARD, UNDEFINED
    gateway: str = "asaas"  # asaas, stripe, mercadopago


class CheckoutResponse(BaseModel):
    invoice_id: uuid.UUID
    gateway_id: str
    checkout_url: str | None = None
    pix_qr_code: str | None = None
    pix_copy_paste: str | None = None
    boleto_url: str | None = None
    status: str = "pending"


class UpgradeRequestCreate(BaseModel):
    target_plan_id: uuid.UUID


class UpgradeRequestResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    user_email: str | None = None
    current_plan_name: str | None = None
    target_plan_name: str | None = None
    target_plan_price: float | None = None
    mt5_balance: float
    status: str
    admin_note: str | None = None
    created_at: datetime
    resolved_at: datetime | None = None


class UpgradeRequestAction(BaseModel):
    action: str  # "approve" or "reject"
    note: str | None = None


# ── Admin schemas ─────────────────────────────────────────

class AdminSubscriptionResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    user_email: str | None = None
    plan_name: str | None = None
    plan_price: float | None = None
    status: str
    trial_start: datetime
    trial_end: datetime | None
    current_period_start: datetime | None
    current_period_end: datetime | None
    next_billing_date: datetime | None = None
    auto_renew: bool
    created_at: datetime

    class Config:
        from_attributes = True


class AdminInvoiceResponse(BaseModel):
    id: uuid.UUID
    subscription_id: uuid.UUID
    user_email: str | None = None
    plan_name: str | None = None
    amount: float
    currency: str
    status: str
    issue_date: datetime
    due_date: datetime
    paid_at: datetime | None
    provider: str | None
    external_id: str | None = None

    class Config:
        from_attributes = True


class AdminCancelSubscriptionRequest(BaseModel):
    reason: str | None = None


class AdminRefundRequest(BaseModel):
    invoice_id: uuid.UUID
    amount: float | None = None  # None = full refund
    reason: str | None = None


class BillingStatsResponse(BaseModel):
    total_revenue: float = 0
    active_subscriptions: int = 0
    trial_subscriptions: int = 0
    blocked_subscriptions: int = 0
    pending_invoices: int = 0
    overdue_invoices: int = 0
    paid_invoices_this_month: int = 0
