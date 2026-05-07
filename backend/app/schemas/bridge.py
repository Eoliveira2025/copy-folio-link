"""Pydantic schemas for the Bridge API."""

from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator


BridgeAction = Literal["OPEN", "CLOSE", "MODIFY", "SLTP"]
BridgeOrderType = Literal["BUY", "SELL", "BUY_LIMIT", "SELL_LIMIT", "BUY_STOP", "SELL_STOP"]


class BridgeSignalIn(BaseModel):
    master_id: str = Field(..., min_length=1, max_length=128)
    strategy_id: Optional[str] = Field(default=None, max_length=64)
    action: BridgeAction
    symbol: str = Field(..., min_length=1, max_length=32)
    order_type: Optional[BridgeOrderType] = None
    volume: float = Field(..., gt=0)
    price: Optional[float] = None
    sl: Optional[float] = None
    tp: Optional[float] = None
    master_ticket: Optional[str] = Field(default=None, max_length=64)
    position_id: Optional[str] = Field(default=None, max_length=64)
    master_balance: Optional[float] = None

    @field_validator("symbol")
    @classmethod
    def symbol_strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("symbol must not be empty")
        return v


class BridgeSignalAck(BaseModel):
    status: str
    signal_id: str
