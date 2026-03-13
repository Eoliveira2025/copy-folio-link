"""Data classes for trade events flowing through the engine."""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
import json
import uuid


class TradeAction(str, Enum):
    OPEN = "open"
    CLOSE = "close"
    MODIFY = "modify"


class TradeDirection(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class CopyStatus(str, Enum):
    PENDING = "pending"
    EXECUTING = "executing"
    EXECUTED = "executed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class TradeEvent:
    """Represents a detected change on a master account."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    master_account_id: str = ""
    master_login: int = 0
    ticket: int = 0
    symbol: str = ""
    action: TradeAction = TradeAction.OPEN
    direction: TradeDirection = TradeDirection.BUY
    volume: float = 0.0
    price: float = 0.0
    sl: Optional[float] = None
    tp: Optional[float] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str) -> TradeEvent:
        d = json.loads(data)
        d["action"] = TradeAction(d["action"])
        d["direction"] = TradeDirection(d["direction"])
        return cls(**d)


@dataclass
class CopyOrder:
    """A trade to be executed on a client account."""
    order_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_id: str = ""
    client_mt5_account_id: str = ""
    client_login: int = 0
    client_server: str = ""
    symbol: str = ""
    action: TradeAction = TradeAction.OPEN
    direction: TradeDirection = TradeDirection.BUY
    volume: float = 0.0
    price: float = 0.0
    sl: Optional[float] = None
    tp: Optional[float] = None
    master_ticket: int = 0
    status: CopyStatus = CopyStatus.PENDING
    attempt: int = 0
    error: Optional[str] = None

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str) -> CopyOrder:
        d = json.loads(data)
        d["action"] = TradeAction(d["action"])
        d["direction"] = TradeDirection(d["direction"])
        d["status"] = CopyStatus(d["status"])
        return cls(**d)
