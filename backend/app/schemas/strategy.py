"""Strategy schemas."""

from pydantic import BaseModel
import uuid


class StrategyResponse(BaseModel):
    id: uuid.UUID
    level: str
    name: str
    description: str | None
    risk_multiplier: float
    requires_unlock: bool
    is_available: bool = False  # computed per-user

    class Config:
        from_attributes = True


class SelectStrategyRequest(BaseModel):
    strategy_id: uuid.UUID


class MasterMappingResponse(BaseModel):
    strategy: str
    master_account_name: str
    account_id: int

    class Config:
        from_attributes = True
