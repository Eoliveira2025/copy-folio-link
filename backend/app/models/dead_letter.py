"""Dead letter queue model for failed trade executions."""

import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Float, Boolean, Text, Integer, BigInteger
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class DeadLetterStatus(str, enum.Enum):
    PENDING = "pending"
    RETRIED = "retried"
    RESOLVED = "resolved"


class DeadLetterTrade(Base):
    __tablename__ = "dead_letter_trades"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    order_id: Mapped[str] = mapped_column(String(100), nullable=False)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    action: Mapped[str] = mapped_column(String(10), nullable=False)
    direction: Mapped[str] = mapped_column(String(4), nullable=False)
    volume: Mapped[float] = mapped_column(Float, nullable=False)
    master_ticket: Mapped[int] = mapped_column(BigInteger, nullable=False)
    client_mt5_id: Mapped[str] = mapped_column(String(100), nullable=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=1)
    raw_payload: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[DeadLetterStatus] = mapped_column(
        default=DeadLetterStatus.PENDING, nullable=False
    )
    resolution_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
