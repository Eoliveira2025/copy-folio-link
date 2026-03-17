"""Strategy, MasterAccount, and UserStrategy models."""

import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import String, ForeignKey, DateTime, Enum as SAEnum, Boolean, Float, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class StrategyLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    PRO = "pro"
    EXPERT = "expert"
    EXPERT_PRO = "expert_pro"


# Strategies that require admin unlock
LOCKED_STRATEGIES = {StrategyLevel.PRO, StrategyLevel.EXPERT, StrategyLevel.EXPERT_PRO}


class Strategy(Base):
    __tablename__ = "strategies"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    level: Mapped[StrategyLevel] = mapped_column(SAEnum(StrategyLevel), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    risk_multiplier: Mapped[float] = mapped_column(Float, default=1.0)
    requires_unlock: Mapped[bool] = mapped_column(Boolean, default=False)

    master_account = relationship("MasterAccount", back_populates="strategy", uselist=False)


class MasterAccount(Base):
    __tablename__ = "master_accounts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    strategy_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("strategies.id"), unique=True, nullable=False)
    account_name: Mapped[str] = mapped_column(String(255), nullable=False)
    login: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    server: Mapped[str] = mapped_column(String(255), nullable=False)
    balance: Mapped[float] = mapped_column(Float, default=0.0)

    strategy = relationship("Strategy", back_populates="master_account")
    trade_events = relationship("TradeEvent", back_populates="master_account", cascade="all, delete-orphan")


class UserStrategy(Base):
    __tablename__ = "user_strategies"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    strategy_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("strategies.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    unlocked_by_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    activated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="user_strategies")
    strategy = relationship("Strategy")
