"""Copy recovery audit model.

One row per recovery attempt (open_recovery or close_recovery).
Provides full audit trail for the Admin > Operations panel.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Float, Integer, BigInteger, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from app.core.database import Base


# ── Standardized reason codes ──────────────────────────────────────
# OPEN
REASON_INSUFFICIENT_MARGIN = "insufficient_margin"
REASON_MARKET_CLOSED = "market_closed"
REASON_SYMBOL_NOT_FOUND = "symbol_not_found"
REASON_VOLUME_INVALID = "volume_invalid"
REASON_ACCOUNT_DISCONNECTED = "account_disconnected"
REASON_TRADE_CONTEXT_BUSY = "trade_context_busy"
REASON_PRICE_OFF_QUOTES = "price_off_quotes"
REASON_REQUOTE = "requote"
REASON_UNSUPPORTED_FILLING = "unsupported_filling_mode"
REASON_RETRY_REJECTED_FAVORABLE = "retry_rejected_favorable_move"
REASON_RETRY_WINDOW_EXPIRED = "retry_window_expired"
REASON_RETRY_SUCCESS = "retry_success"
REASON_RETRY_FAILED_FINAL = "retry_failed_final"
# CLOSE
REASON_CLOSE_RETRYING = "close_retrying"
REASON_CLOSE_RETRY_SUCCESS = "close_retry_success"
REASON_CLOSE_RETRY_FAILED = "close_retry_failed"
REASON_NO_POSITION_TO_CLOSE = "no_position_to_close"
REASON_MANUALLY_CLOSED = "manually_closed_by_user_possible"
REASON_CLOSE_MAX_ATTEMPTS = "close_retry_max_attempts_reached"

# Statuses
STATUS_FAILED_RETRYABLE = "failed_retryable"
STATUS_RETRIED_SUCCESS = "retried_success"
STATUS_RETRIED_REJECTED = "retried_rejected"
STATUS_CLOSE_RETRYING = "close_retrying"
STATUS_CLOSE_RETRY_SUCCESS = "close_retry_success"
STATUS_CLOSE_RETRY_FAILED = "close_retry_failed"
STATUS_NO_POSITION_TO_CLOSE = "no_position_to_close"

# Decisions
DECISION_RETRY_ALLOWED = "retry_allowed"
DECISION_RETRY_REJECTED = "retry_rejected"
DECISION_RETRY_EXECUTED = "retry_executed"
DECISION_RETRY_FATAL = "retry_fatal"
DECISION_INFORMATIONAL = "informational"


class TradeCopyRecovery(Base):
    """Single recovery attempt on a failed copy trade."""

    __tablename__ = "trade_copy_recoveries"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trade_copy_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True, index=True)
    order_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    mt5_account_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True, index=True)

    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    action: Mapped[str] = mapped_column(String(10), nullable=False)
    direction: Mapped[str] = mapped_column(String(4), nullable=False)
    volume: Mapped[float] = mapped_column(Float, nullable=False)
    master_ticket: Mapped[int] = mapped_column(BigInteger, nullable=False)
    client_ticket: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    recovery_type: Mapped[str] = mapped_column(String(32), nullable=False)  # open_recovery / close_recovery
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    decision: Mapped[str] = mapped_column(String(64), nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False)

    original_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_delta_points: Mapped[float | None] = mapped_column(Float, nullable=True)

    mt5_retcode: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mt5_retcode_comment: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
