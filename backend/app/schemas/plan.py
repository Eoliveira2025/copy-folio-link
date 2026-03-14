"""Plan schemas."""

from pydantic import BaseModel, field_validator
import uuid

ALLOWED_CURRENCIES = ("USD", "BRL")


class PlanResponse(BaseModel):
    id: uuid.UUID
    name: str
    price: float
    currency: str
    allowed_strategies: list[str]
    trial_days: int
    max_accounts: int
    active: bool

    class Config:
        from_attributes = True


class PlanCreate(BaseModel):
    name: str
    price: float
    currency: str = "USD"
    allowed_strategies: list[str]
    trial_days: int = 30
    max_accounts: int = 1
    active: bool = True

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        v = v.upper()
        if v not in ALLOWED_CURRENCIES:
            raise ValueError(f"Currency must be one of {ALLOWED_CURRENCIES}")
        return v


class PlanUpdate(BaseModel):
    name: str | None = None
    price: float | None = None
    currency: str | None = None
    allowed_strategies: list[str] | None = None
    trial_days: int | None = None
    max_accounts: int | None = None
    active: bool | None = None

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.upper()
        if v not in ALLOWED_CURRENCIES:
            raise ValueError(f"Currency must be one of {ALLOWED_CURRENCIES}")
        return v


class ChangePlanRequest(BaseModel):
    plan_id: uuid.UUID
