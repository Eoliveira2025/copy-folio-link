"""
Data models for ultra-low-latency trade event streaming.

Key design decisions for <100ms latency:
  - time.monotonic_ns() for latency measurement (no clock drift)
  - time.time() epoch floats for timestamps (faster than datetime)
  - msgpack-compatible dict serialization (orjson for speed)
  - Slippage control fields on CopyOrder
  - Per-hop latency tracking: detect_ns → distribute_ns → execute_ns
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional
import time
import uuid

try:
    import orjson
    def _dumps(d: dict) -> str:
        return orjson.dumps(d).decode()
    def _loads(s) -> dict:
        return orjson.loads(s)
except ImportError:
    import json
    _dumps = json.dumps
    _loads = json.loads


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
    SLIPPAGE_REJECTED = "slippage_rejected"


@dataclass
class TradeEvent:
    """
    Represents a detected trade change on a master account.

    Latency path:
      detected_at_ns (monotonic) → published to Redis → consumed by distributor
    """
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex)
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
    magic_number: int = 0
    # Timing — epoch seconds (float) for cross-process compatibility
    detected_at: float = field(default_factory=time.time)
    # Monotonic ns for same-process latency measurement
    detected_at_ns: int = field(default_factory=time.monotonic_ns)

    def to_json(self) -> str:
        d = asdict(self)
        d["action"] = self.action.value
        d["direction"] = self.direction.value
        return _dumps(d)

    @classmethod
    def from_json(cls, data) -> TradeEvent:
        d = _loads(data) if isinstance(data, (str, bytes)) else data
        d["action"] = TradeAction(d["action"])
        d["direction"] = TradeDirection(d["direction"])
        return cls(**d)


@dataclass
class CopyOrder:
    """
    A trade to be executed on a client account with full latency tracking.

    Latency hops:
      detect → distribute → enqueue → dequeue → execute → result
    """
    order_id: str = field(default_factory=lambda: uuid.uuid4().hex)
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
    magic_number: int = 123456
    status: CopyStatus = CopyStatus.PENDING
    attempt: int = 0
    max_attempts: int = 3
    error: Optional[str] = None

    # Recovery layer (opt-in, set by recovery worker)
    is_recovery: bool = False
    recovery_type: Optional[str] = None   # open_recovery / close_recovery
    recovery_attempt: int = 0
    recovery_max_attempts: int = 0
    original_master_price: float = 0.0    # snapshot at first failure

    # MT5 raw outcome (populated on failure for recovery worker)
    mt5_retcode: Optional[int] = None
    mt5_retcode_comment: Optional[str] = None

    # Slippage control
    max_slippage_points: int = 30  # Maximum allowed slippage
    master_price: float = 0.0  # Original master price for slippage calc
    executed_price: float = 0.0  # Actual fill price
    slippage_points: float = 0.0  # Calculated slippage

    # Latency tracking (epoch seconds)
    event_detected_at: float = 0.0  # When master trade was detected
    distributed_at: float = 0.0  # When distributor created this order
    enqueued_at: float = 0.0  # When pushed to execution queue
    dequeued_at: float = 0.0  # When executor picked it up
    executed_at: float = 0.0  # When MT5 order_send returned
    result_at: float = 0.0  # When result was published

    # Computed latencies (ms)
    latency_detect_to_distribute_ms: float = 0.0
    latency_distribute_to_execute_ms: float = 0.0
    latency_total_ms: float = 0.0  # detect → execute

    def compute_latencies(self):
        """Calculate all latency hops."""
        if self.event_detected_at and self.distributed_at:
            self.latency_detect_to_distribute_ms = (self.distributed_at - self.event_detected_at) * 1000
        if self.distributed_at and self.executed_at:
            self.latency_distribute_to_execute_ms = (self.executed_at - self.distributed_at) * 1000
        if self.event_detected_at and self.executed_at:
            self.latency_total_ms = (self.executed_at - self.event_detected_at) * 1000

    def to_json(self) -> str:
        d = asdict(self)
        d["action"] = self.action.value
        d["direction"] = self.direction.value
        d["status"] = self.status.value
        return _dumps(d)

    @classmethod
    def from_json(cls, data) -> CopyOrder:
        d = _loads(data) if isinstance(data, (str, bytes)) else data
        d["action"] = TradeAction(d["action"])
        d["direction"] = TradeDirection(d["direction"])
        d["status"] = CopyStatus(d["status"])
        return cls(**d)
