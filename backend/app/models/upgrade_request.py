"""Upgrade Request model for manual plan upgrade approval."""

import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import String, ForeignKey, DateTime, Enum as SAEnum, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class UpgradeRequestStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class UpgradeRequest(Base):
    __tablename__ = "upgrade_requests"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    current_plan_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("plans.id"))
    target_plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("plans.id"), nullable=False)
    mt5_balance: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[UpgradeRequestStatus] = mapped_column(
        SAEnum(UpgradeRequestStatus), default=UpgradeRequestStatus.PENDING
    )
    admin_note: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user = relationship("User", backref="upgrade_requests")
    current_plan = relationship("Plan", foreign_keys=[current_plan_id])
    target_plan = relationship("Plan", foreign_keys=[target_plan_id])
