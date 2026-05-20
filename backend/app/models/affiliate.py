import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import String, ForeignKey, DateTime, Enum as SAEnum, Boolean, Text, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

class CommissionBase(str, enum.Enum):
    COMPANY_COMMISSION = "COMPANY_COMMISSION"
    GROSS_PROFIT = "GROSS_PROFIT"

class CommissionStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    PAID = "PAID"
    CANCELLED = "CANCELLED"

class Affiliate(Base):
    __tablename__ = "affiliates"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    commission_percentage: Mapped[float] = mapped_column(Numeric(10, 2), default=20.0)
    commission_base: Mapped[CommissionBase] = mapped_column(SAEnum(CommissionBase), default=CommissionBase.COMPANY_COMMISSION)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user = relationship("User", foreign_keys=[user_id])
    referrals = relationship("AffiliateReferral", back_populates="affiliate", cascade="all, delete-orphan")
    commissions = relationship("AffiliateCommission", back_populates="affiliate", cascade="all, delete-orphan")

class AffiliateReferral(Base):
    __tablename__ = "affiliate_referrals"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    affiliate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("affiliates.id", ondelete="CASCADE"), index=True)
    referred_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    affiliate = relationship("Affiliate", back_populates="referrals")
    referred_user = relationship("User", foreign_keys=[referred_user_id])

class AffiliateCommission(Base):
    __tablename__ = "affiliate_commissions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    affiliate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("affiliates.id", ondelete="CASCADE"), index=True)
    referred_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    performance_cycle_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("performance_billing_cycles.id", ondelete="SET NULL"))
    gross_profit: Mapped[float] = mapped_column(Numeric(18, 2), default=0.0)
    company_commission_amount: Mapped[float] = mapped_column(Numeric(18, 2), default=0.0)
    affiliate_percentage: Mapped[float] = mapped_column(Numeric(10, 2))
    commission_base: Mapped[CommissionBase] = mapped_column(SAEnum(CommissionBase))
    affiliate_commission_amount: Mapped[float] = mapped_column(Numeric(18, 2))
    status: Mapped[CommissionStatus] = mapped_column(SAEnum(CommissionStatus), default=CommissionStatus.PENDING)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    affiliate = relationship("Affiliate", back_populates="commissions")
    referred_user = relationship("User")
    cycle = relationship("PerformanceBillingCycle")
