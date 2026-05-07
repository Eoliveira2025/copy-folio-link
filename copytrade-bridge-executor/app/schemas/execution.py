"""Execution payloads."""
from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field


Action = Literal["OPEN", "CLOSE", "MODIFY", "SLTP"]
OrderType = Literal["BUY", "SELL", "BUY_LIMIT", "SELL_LIMIT", "BUY_STOP", "SELL_STOP"]
ResultStatus = Literal["executed", "failed", "simulated", "skipped"]


class ExecutionOrder(BaseModel):
    execution_order_id: str
    client_login: str
    client_server: Optional[str] = None
    client_password: Optional[str] = None
    mt5_account_id: Optional[str] = None

    action: Action
    symbol: str
    order_type: Optional[OrderType] = None
    lot: float = Field(gt=0)
    price: Optional[float] = None
    sl: Optional[float] = None
    tp: Optional[float] = None
    master_ticket: Optional[str] = None
    strategy_id: Optional[str] = None


class ExecutionResult(BaseModel):
    execution_order_id: str
    executor_id: str
    client_login: str
    status: ResultStatus
    action: Action
    symbol: str
    lot: float
    mt5_order: Optional[str] = None
    mt5_position: Optional[str] = None
    retcode: Optional[int] = None
    message: str = ""
    error: Optional[str] = None
    executed_at: str
