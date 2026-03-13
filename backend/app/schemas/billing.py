"""Subscription and Invoice schemas."""

from pydantic import BaseModel
from datetime import datetime
import uuid


class SubscriptionResponse(BaseModel):
    id: uuid.UUID
    status: str
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
