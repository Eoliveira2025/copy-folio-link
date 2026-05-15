import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import String, ForeignKey, DateTime, Enum as SAEnum, Boolean, Float, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

class MetaApiAccountType(str, enum.Enum):
    MASTER = "MASTER"
    CLIENT = "CLIENT"

class MetaApiAccount(Base):
    __tablename__ = "metaapi_accounts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    login: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    server: Mapped[str] = mapped_column(String(100), nullable=False)
    metaapi_account_id: Mapped[str | None] = mapped_column(String(100), unique=True)
    account_type: Mapped[MetaApiAccountType] = mapped_column(SAEnum(MetaApiAccountType), default=MetaApiAccountType.CLIENT)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    deployment_status: Mapped[str] = mapped_column(String(50), default="UNDEPLOYED")
    connection_status: Mapped[str] = mapped_column(String(50), default="DISCONNECTED")
    copyfactory_strategy_id: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class MetaApiSubscription(Base):
    __tablename__ = "metaapi_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    client_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("metaapi_accounts.id", ondelete="CASCADE"), nullable=False)
    master_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("metaapi_accounts.id", ondelete="CASCADE"), nullable=False)
    copyfactory_subscription_id: Mapped[str | None] = mapped_column(String(100))
    risk_ratio: Mapped[float] = mapped_column(Float, default=1.0)
    status: Mapped[str] = mapped_column(String(50), default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class MetaApiEvent(Base):
    __tablename__ = "metaapi_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("metaapi_accounts.id", ondelete="SET NULL"))
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
