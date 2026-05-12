"""Dry-run order task contract for V2.

Increment 3: NO real `mt5.order_send`. Tasks are validated, logged and
acknowledged. Real execution lands in increment 6.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID, uuid4


class OrderAction(str, enum.Enum):
    OPEN = "OPEN"
    CLOSE = "CLOSE"
    MODIFY = "MODIFY"


class OrderSide(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"


class TaskStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED = "FAILED"
    DUPLICATE = "DUPLICATE"


@dataclass
class OrderTask:
    """Unit of work flowing through ExecutionQueue."""

    account_id: UUID
    pool_id: UUID
    terminal_id: UUID
    master_id: UUID
    strategy_id: UUID
    action: OrderAction
    symbol: str

    # OPEN
    side: Optional[OrderSide] = None
    volume: Optional[float] = None
    sl: Optional[float] = None
    tp: Optional[float] = None

    # CLOSE / MODIFY
    client_ticket: Optional[int] = None
    master_ticket: Optional[int] = None
    magic: int = 0
    comment: Optional[str] = None

    # control
    idempotency_key: str = ""
    task_id: UUID = field(default_factory=uuid4)
    status: TaskStatus = TaskStatus.QUEUED
    failure_reason: Optional[str] = None

    def __post_init__(self):
        if not self.idempotency_key:
            # Default key: stable for the same logical event
            base = (
                f"{self.account_id}:{self.action.value}:{self.symbol}:"
                f"{self.master_ticket or ''}:{self.client_ticket or ''}"
            )
            self.idempotency_key = base

    def log_fields(self) -> dict:
        return {
            "task_id": str(self.task_id),
            "account_id": str(self.account_id),
            "pool_id": str(self.pool_id),
            "terminal_id": str(self.terminal_id),
            "master_id": str(self.master_id),
            "strategy_id": str(self.strategy_id),
            "action": self.action.value,
            "order_id": self.idempotency_key,
        }
