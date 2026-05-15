import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import String, ForeignKey, DateTime, Enum as SAEnum, Boolean, Float, Text, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

class MetaApiAccountType(str, enum.Enum):
    MASTER = "MASTER"
    CLIENT = "CLIENT"

class MetaApiAccount(Base):
    __tablename__ = "metaapi_accounts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=True)
    login: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    server: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    account_type: Mapped[str] = mapped_column(String(20), default="CLIENT") # MASTER or CLIENT
    metaapi_account_id: Mapped[str | None] = mapped_column(String(100), unique=True)
    deployment_status: Mapped[str] = mapped_column(String(50), default="UNDEPLOYED")
    connection_status: Mapped[str] = mapped_column(String(50), default="DISCONNECTED")
    
    # Metrics
    last_balance: Mapped[float] = mapped_column(Float, default=0.0)
    last_equity: Mapped[float] = mapped_column(Float, default=0.0)
    last_margin: Mapped[float] = mapped_column(Float, default=0.0)
    last_free_margin: Mapped[float] = mapped_column(Float, default=0.0)
    last_profit_loss: Mapped[float] = mapped_column(Float, default=0.0)
    last_positions_count: Mapped[int] = mapped_column(Integer, default=0)
    last_positions_json: Mapped[dict | None] = mapped_column(JSON)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class CopyFactoryStrategy(Base):
    __tablename__ = "copyfactory_strategies"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    strategy_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False) # LOW, MEDIUM, etc.
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    master_account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("metaapi_accounts.id", ondelete="SET NULL"))
    copyfactory_strategy_id: Mapped[str | None] = mapped_column(String(100), unique=True)
    min_balance: Mapped[float] = mapped_column(Float, default=0.0)
    risk_multiplier_default: Mapped[float] = mapped_column(Float, default=1.0)
    copy_sl: Mapped[bool] = mapped_column(Boolean, default=True)
    copy_tp: Mapped[bool] = mapped_column(Boolean, default=True)
    open_small_trades: Mapped[bool] = mapped_column(Boolean, default=True)
    do_not_scale: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class CopyFactorySubscription(Base):
    __tablename__ = "copyfactory_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    client_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("metaapi_accounts.id", ondelete="CASCADE"), nullable=False)
    strategy_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("copyfactory_strategies.id", ondelete="CASCADE"), nullable=False)
    copyfactory_subscription_id: Mapped[str | None] = mapped_column(String(100), unique=True)
    status: Mapped[str] = mapped_column(String(50), default="PENDING") # ACTIVE, PAUSED, PENDING, ERROR
    risk_ratio: Mapped[float] = mapped_column(Float, default=1.0)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class StrategySwitchRequest(Base):
    __tablename__ = "strategy_switch_requests"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    current_strategy_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("copyfactory_strategies.id", ondelete="SET NULL"))
    target_strategy_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("copyfactory_strategies.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="REQUESTED") # REQUESTED, PENDING_WAIT_FLAT, SWITCHED, CANCELLED, FAILED, FORCED
    has_open_positions_at_request: Mapped[bool] = mapped_column(Boolean, default=False)
    open_positions_snapshot: Mapped[dict | None] = mapped_column(JSON)
    requested_by: Mapped[str] = mapped_column(String(50), default="user") # user, admin, system
    forced_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    switched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class MetaApiAccountMetric(Base):
    __tablename__ = "metaapi_account_metrics"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("metaapi_accounts.id", ondelete="CASCADE"), index=True, nullable=False)
    balance: Mapped[float] = mapped_column(Float, default=0.0)
    equity: Mapped[float] = mapped_column(Float, default=0.0)
    margin: Mapped[float] = mapped_column(Float, default=0.0)
    free_margin: Mapped[float] = mapped_column(Float, default=0.0)
    profit_loss: Mapped[float] = mapped_column(Float, default=0.0)
    positions_count: Mapped[int] = mapped_column(Integer, default=0)
    positions_json: Mapped[dict | None] = mapped_column(JSON)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class MetaApiEvent(Base):
    __tablename__ = "metaapi_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("metaapi_accounts.id", ondelete="SET NULL"))
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class MetaApiReconciliationSettings(Base):
    __tablename__ = "metaapi_reconciliation_settings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    auto_close_orphan_positions: Mapped[bool] = mapped_column(Boolean, default=True)
    orphan_auto_close_loss_limit: Mapped[float] = mapped_column(Float, default=-2.00)
    orphan_auto_close_profit_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    lot_tolerance: Mapped[float] = mapped_column(Float, default=0.01)
    strict_symbol_match: Mapped[bool] = mapped_column(Boolean, default=True)
    price_tolerance_points: Mapped[int] = mapped_column(Integer, default=50)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class PositionReconciliationEvent(Base):
    __tablename__ = "position_reconciliation_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("metaapi_accounts.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    master_account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("metaapi_accounts.id", ondelete="SET NULL"))
    subscriber_account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("metaapi_accounts.id", ondelete="SET NULL"))
    symbol: Mapped[str] = mapped_column(String(50), nullable=False)
    position_id: Mapped[str] = mapped_column(String(100), nullable=False)
    side: Mapped[str] = mapped_column(String(10), nullable=False) # BUY/SELL
    volume: Mapped[float] = mapped_column(Float, nullable=False)
    open_price: Mapped[float] = mapped_column(Float, nullable=False)
    current_price: Mapped[float] = mapped_column(Float, nullable=False)
    profit: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False) # ORPHAN_DETECTED, AUTO_CLOSED, WAITING_ADMIN_APPROVAL, ADMIN_CLOSED, IGNORED, FAILED
    reason: Mapped[str | None] = mapped_column(Text)
    snapshot_master_positions: Mapped[dict | None] = mapped_column(JSON)
    snapshot_subscriber_positions: Mapped[dict | None] = mapped_column(JSON)
    action_taken: Mapped[str | None] = mapped_column(String(100))
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
