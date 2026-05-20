import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import String, ForeignKey, DateTime, Enum as SAEnum, Float, Boolean, Text, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

class BillingMethodType(str, enum.Enum):
    MONTHLY = "MONTHLY"
    PERFORMANCE_WEEKLY = "PERFORMANCE_WEEKLY"

class CycleStatus(str, enum.Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    INVOICED = "INVOICED"
    NO_PROFIT = "NO_PROFIT"
    ERROR = "ERROR"

class BillingMethod(Base):
    __tablename__ = "billing_methods"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False, unique=True)
    method: Mapped[BillingMethodType] = mapped_column(SAEnum(BillingMethodType), default=BillingMethodType.MONTHLY)
    performance_percentage: Mapped[float] = mapped_column(Numeric(10, 2), default=30.0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    created_by: Mapped[str | None] = mapped_column(String(255))

    user = relationship("User")

class PerformanceBillingCycle(Base):
    __tablename__ = "performance_billing_cycles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    account_source: Mapped[str] = mapped_column(String(50)) # metaapi or mt5
    account_login: Mapped[str] = mapped_column(String(50))
    strategy_code: Mapped[str | None] = mapped_column(String(50))
    cycle_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    cycle_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    start_balance: Mapped[float] = mapped_column(Numeric(18, 2))
    end_balance: Mapped[float | None] = mapped_column(Numeric(18, 2))
    gross_profit: Mapped[float | None] = mapped_column(Numeric(18, 2))
    commission_percentage: Mapped[float] = mapped_column(Numeric(10, 2))
    commission_amount: Mapped[float | None] = mapped_column(Numeric(18, 2))
    status: Mapped[CycleStatus] = mapped_column(SAEnum(CycleStatus), default=CycleStatus.OPEN)
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("invoices.id", ondelete="SET NULL"))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user = relationship("User")
    invoice = relationship("Invoice")
