"""Plan schemas."""

from pydantic import BaseModel
import uuid


class PlanResponse(BaseModel):
    id: uuid.UUID
    name: str
    price: float
    allowed_strategies: list[str]
    trial_days: int
    max_accounts: int
    active: bool

    class Config:
        from_attributes = True


class PlanCreate(BaseModel):
    name: str
    price: float
    allowed_strategies: list[str]
    trial_days: int = 30
    max_accounts: int = 1
    active: bool = True


class PlanUpdate(BaseModel):
    name: str | None = None
    price: float | None = None
    allowed_strategies: list[str] | None = None
    trial_days: int | None = None
    max_accounts: int | None = None
    active: bool | None = None


class ChangePlanRequest(BaseModel):
    plan_id: uuid.UUID
