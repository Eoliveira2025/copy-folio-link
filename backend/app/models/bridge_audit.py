"""Bridge Auditor model — one row per audit check on a copy execution."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Numeric, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB

from app.core.database import Base


# Possible statuses
AUDIT_PENDING = "pending"
AUDIT_MATCHED = "matched"
AUDIT_NOT_EXECUTED = "not_executed"
AUDIT_WRONG_LOT = "wrong_lot"
AUDIT_WRONG_SYMBOL = "wrong_symbol"
AUDIT_WRONG_DIRECTION = "wrong_direction"
AUDIT_SLTP_MISMATCH = "sl_tp_mismatch"
AUDIT_ALREADY_CLOSED = "already_closed"
AUDIT_ORPHAN_FOUND = "orphan_position_found"
AUDIT_AUTO_FIXED = "auto_fixed"
AUDIT_AUTO_FIX_FAILED = "auto_fix_failed"
AUDIT_FAILED_TO_CHECK = "failed_to_check"
AUDIT_STILL_OPEN = "still_open"


class BridgeAudit(Base):
    __tablename__ = "bridge_audits"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bridge_execution_order_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    bridge_signal_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    mt5_account_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    client_login: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    expected_action: Mapped[str] = mapped_column(String(16), nullable=False)
    expected_symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    expected_order_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    expected_lot: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    expected_sl: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    expected_tp: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    master_ticket: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    audit_status: Mapped[str] = mapped_column(String(32), nullable=False, default=AUDIT_PENDING, index=True)
    detected_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    auto_fix_attempted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    auto_fix_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    raw_check_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
