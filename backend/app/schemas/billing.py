"""Subscription, Invoice, and Upgrade Request schemas."""

from pydantic import BaseModel
from datetime import datetime
import uuid


class SubscriptionResponse(BaseModel):
    id: uuid.UUID
    status: str
    plan_name: str | None = None
    plan_price: float | None = None
    trial_start: datetime
    trial_end: datetime | None
    current_period_start: datetime | None
    current_period_end: datetime | None
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

    class Config:
        from_attributes = True


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
