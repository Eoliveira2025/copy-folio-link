"""Bridge persistence models: bridge_signals and bridge_execution_orders."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Numeric, Text, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB

from app.core.database import Base


class BridgeSignal(Base):
    __tablename__ = "bridge_signals"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    master_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    strategy_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    master_ticket: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    position_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    order_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    volume: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    price: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    sl: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    tp: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    master_balance: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="received", index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BridgeExecutionOrder(Base):
    __tablename__ = "bridge_execution_orders"
    __table_args__ = (
        UniqueConstraint("bridge_signal_id", "mt5_account_id", "action", name="uq_bridge_exec_signal_account_action"),
        Index("ix_bridge_exec_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bridge_signal_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("bridge_signals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    mt5_account_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    client_login: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    order_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    calculated_lot: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    price: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    sl: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    tp: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    redis_queue: Mapped[str] = mapped_column(String(128), nullable=False)
    result_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
