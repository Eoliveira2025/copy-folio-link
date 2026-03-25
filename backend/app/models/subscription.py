"""Subscription model with plan linkage, free trial, recurring billing, and access control."""

import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import ForeignKey, DateTime, Enum as SAEnum, Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class SubscriptionStatus(str, enum.Enum):
    TRIAL = "trial"
    ACTIVE = "active"
    EXPIRED = "expired"
    BLOCKED = "blocked"


class AccessStatus(str, enum.Enum):
    ACTIVE = "active"
    WARNING = "warning"
    GRACE = "grace"
    BLOCKED = "blocked"


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    plan_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("plans.id"), index=True)
    status: Mapped[SubscriptionStatus] = mapped_column(SAEnum(SubscriptionStatus), default=SubscriptionStatus.TRIAL)
    access_status: Mapped[AccessStatus] = mapped_column(
        SAEnum(AccessStatus, name="accessstatus", create_constraint=False),
        default=AccessStatus.ACTIVE,
        server_default="active",
    )
    manual_override: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    last_access_check: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    blocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    trial_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    trial_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    auto_renew: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Recurring billing fields
    next_billing_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    billing_cycle_days: Mapped[int] = mapped_column(Integer, default=30)

    user = relationship("User", back_populates="subscriptions")
    plan = relationship("Plan", back_populates="subscriptions")
    invoices = relationship("Invoice", back_populates="subscription", cascade="all, delete-orphan")
