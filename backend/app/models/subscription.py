"""Subscription model with plan linkage and free trial support."""

import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import ForeignKey, DateTime, Enum as SAEnum, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class SubscriptionStatus(str, enum.Enum):
    TRIAL = "trial"
    ACTIVE = "active"
    EXPIRED = "expired"
    BLOCKED = "blocked"


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    plan_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("plans.id"), index=True)
    status: Mapped[SubscriptionStatus] = mapped_column(SAEnum(SubscriptionStatus), default=SubscriptionStatus.TRIAL)
    trial_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    trial_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    auto_renew: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="subscriptions")
    plan = relationship("Plan", back_populates="subscriptions")
    invoices = relationship("Invoice", back_populates="subscription", cascade="all, delete-orphan")
