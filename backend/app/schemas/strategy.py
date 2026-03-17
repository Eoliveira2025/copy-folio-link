"""Strategy schemas."""

from pydantic import BaseModel, field_validator
import uuid


class StrategyResponse(BaseModel):
    id: uuid.UUID
    level: str
    name: str
    description: str | None
    risk_multiplier: float
    requires_unlock: bool
    min_capital: float = 0
    is_available: bool = False  # computed per-user
    user_status: str = "available"  # available | active | request | insufficient | locked | pending

    class Config:
        from_attributes = True


class SelectStrategyRequest(BaseModel):
    strategy_id: uuid.UUID


class RequestStrategyRequest(BaseModel):
    strategy_id: uuid.UUID


class MasterMappingResponse(BaseModel):
    strategy: str
    master_account_name: str
    account_id: int

    class Config:
        from_attributes = True


# ── Admin Strategy CRUD Schemas ─────────────────────────

VALID_LEVELS = {"low", "medium", "high", "pro", "expert", "expert_pro"}


class AdminStrategyCreate(BaseModel):
    level: str
    name: str
    description: str | None = None
    risk_multiplier: float = 1.0
    requires_unlock: bool = False
    min_capital: float = 0

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        if v not in VALID_LEVELS:
            raise ValueError(f"level must be one of {VALID_LEVELS}")
        return v

    @field_validator("risk_multiplier")
    @classmethod
    def validate_multiplier(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("risk_multiplier must be positive")
        return v

    @field_validator("min_capital")
    @classmethod
    def validate_min_capital(cls, v: float) -> float:
        if v < 0:
            raise ValueError("min_capital must be >= 0")
        return v


class AdminStrategyUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    risk_multiplier: float | None = None
    requires_unlock: bool | None = None
    min_capital: float | None = None

    @field_validator("risk_multiplier")
    @classmethod
    def validate_multiplier(cls, v: float | None) -> float | None:
        if v is not None and v <= 0:
            raise ValueError("risk_multiplier must be positive")
        return v

    @field_validator("min_capital")
    @classmethod
    def validate_min_capital(cls, v: float | None) -> float | None:
        if v is not None and v < 0:
            raise ValueError("min_capital must be >= 0")
        return v


class AdminStrategyResponse(BaseModel):
    id: uuid.UUID
    level: str
    name: str
    description: str | None
    risk_multiplier: float
    requires_unlock: bool
    min_capital: float = 0
    master_account: "AdminMasterAccountResponse | None" = None

    class Config:
        from_attributes = True


class AdminMasterAccountCreate(BaseModel):
    account_name: str
    login: int
    server: str
    password: str  # Will be encrypted before storage

    @field_validator("login")
    @classmethod
    def validate_login(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("login must be positive")
        return v


class AdminMasterAccountUpdate(BaseModel):
    account_name: str | None = None
    server: str | None = None
    password: str | None = None  # Only update if provided


class AdminMasterAccountResponse(BaseModel):
    id: uuid.UUID
    account_name: str
    login: int
    server: str
    balance: float

    class Config:
        from_attributes = True
