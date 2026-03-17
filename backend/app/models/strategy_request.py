"""StrategyRequest model for strategy upgrade requests."""

import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import String, ForeignKey, DateTime, Enum as SAEnum, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class StrategyRequestStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class StrategyRequest(Base):
    __tablename__ = "strategy_requests"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    current_strategy_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("strategies.id"))
    target_strategy_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("strategies.id"), nullable=False)
    mt5_balance: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[StrategyRequestStatus] = mapped_column(
        SAEnum(StrategyRequestStatus), default=StrategyRequestStatus.PENDING
    )
    admin_note: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user = relationship("User", backref="strategy_requests")
    current_strategy = relationship("Strategy", foreign_keys=[current_strategy_id])
    target_strategy = relationship("Strategy", foreign_keys=[target_strategy_id])
