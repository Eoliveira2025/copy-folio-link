"""MT5 Account schemas."""

from pydantic import BaseModel
from datetime import datetime
import uuid


class ConnectMT5Request(BaseModel):
    login: int
    password: str
    server: str


class MT5AccountResponse(BaseModel):
    id: uuid.UUID
    login: int
    server: str
    status: str
    balance: float | None
    equity: float | None
    last_connected_at: datetime | None

    class Config:
        from_attributes = True


class MT5ServerResponse(BaseModel):
    name: str
    is_active: bool
