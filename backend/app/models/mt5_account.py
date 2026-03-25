"""MT5 Account model – stores encrypted credentials."""

import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import String, ForeignKey, DateTime, Enum as SAEnum, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class MT5Status(str, enum.Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    BLOCKED = "blocked"
    PENDING_PROVISION = "pending_provision"


class MT5Account(Base):
    __tablename__ = "mt5_accounts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    login: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    encrypted_password: Mapped[str] = mapped_column(String(512), nullable=False)
    server: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[MT5Status] = mapped_column(SAEnum(MT5Status), default=MT5Status.PENDING_PROVISION)
    balance: Mapped[float | None] = mapped_column(default=None)
    equity: Mapped[float | None] = mapped_column(default=None)
    last_connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="mt5_accounts")
    trade_copies = relationship("TradeCopy", back_populates="mt5_account", cascade="all, delete-orphan")
