"""TradeEvent and TradeCopy models for the copy engine."""

import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import String, ForeignKey, DateTime, Enum as SAEnum, Float, Integer, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class TradeAction(str, enum.Enum):
    OPEN = "open"
    CLOSE = "close"
    MODIFY = "modify"


class CopyStatus(str, enum.Enum):
    PENDING = "pending"
    EXECUTED = "executed"
    FAILED = "failed"
    SKIPPED = "skipped"


class TradeEvent(Base):
    __tablename__ = "trade_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    master_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("master_accounts.id"), index=True, nullable=False)
    ticket: Mapped[int] = mapped_column(BigInteger, nullable=False)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    action: Mapped[TradeAction] = mapped_column(SAEnum(TradeAction), nullable=False)
    direction: Mapped[str] = mapped_column(String(4), nullable=False)  # BUY / SELL
    volume: Mapped[float] = mapped_column(Float, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    sl: Mapped[float | None] = mapped_column(Float)
    tp: Mapped[float | None] = mapped_column(Float)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    master_account = relationship("MasterAccount", back_populates="trade_events")
    copies = relationship("TradeCopy", back_populates="trade_event", cascade="all, delete-orphan")


class TradeCopy(Base):
    __tablename__ = "trade_copies"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    trade_event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trade_events.id"), index=True, nullable=False)
    mt5_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mt5_accounts.id"), index=True, nullable=False)
    client_ticket: Mapped[int | None] = mapped_column(BigInteger)
    volume: Mapped[float] = mapped_column(Float, nullable=False)
    price: Mapped[float | None] = mapped_column(Float)
    status: Mapped[CopyStatus] = mapped_column(SAEnum(CopyStatus), default=CopyStatus.PENDING)
    error_message: Mapped[str | None] = mapped_column(String(500))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    trade_event = relationship("TradeEvent", back_populates="copies")
    mt5_account = relationship("MT5Account", back_populates="trade_copies")
