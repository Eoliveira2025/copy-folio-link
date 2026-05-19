from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional, List, Literal, Any
from enum import Enum

class MetaApiAccountType(str, Enum):
    MASTER = "MASTER"
    CLIENT = "CLIENT"

class MetaApiAccountCreate(BaseModel):
    login: str
    password: str
    server: str
    name: str
    type: MetaApiAccountType
    strategy_id: Optional[UUID] = None

class MetaApiAccountResponse(BaseModel):
    id: UUID
    user_id: Optional[UUID] = None
    login: str
    server: str
    name: str
    account_type: str
    metaapi_account_id: Optional[str] = None
    deployment_status: str
    connection_status: str
    last_balance: float = 0.0
    last_equity: float = 0.0
    last_profit_loss: float = 0.0
    last_positions_count: int = 0
    last_sync_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True

class CopyFactoryStrategyCreate(BaseModel):
    strategy_code: str
    display_name: str
    master_account_id: Optional[UUID] = None
    min_balance: float = 0.0
    risk_multiplier_default: float = 1.0
    copy_sl: bool = True
    copy_tp: bool = True
    open_small_trades: bool = True
    do_not_scale: bool = False

class CopyFactoryStrategyResponse(BaseModel):
    id: UUID
    strategy_code: str
    display_name: str
    master_account_id: Optional[UUID] = None
    copyfactory_strategy_id: Optional[str] = None
    min_balance: float
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class CopyFactorySubscriptionCreate(BaseModel):
    client_account_id: UUID
    strategy_id: UUID
    risk_ratio: float = 1.0

class CopyFactorySubscriptionResponse(BaseModel):
    id: UUID
    user_id: UUID
    client_account_id: UUID
    strategy_id: UUID
    status: str
    risk_ratio: float
    last_error: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class StrategySwitchRequestCreate(BaseModel):
    target_strategy_id: UUID

class StrategySwitchRequestResponse(BaseModel):
    id: UUID
    user_id: UUID
    current_strategy_id: Optional[UUID] = None
    target_strategy_id: UUID
    status: str
    has_open_positions_at_request: bool
    requested_by: str
    created_at: datetime
    switched_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class MetaApiAccountMetricResponse(BaseModel):
    id: UUID
    account_id: UUID
    balance: float
    equity: float
    profit_loss: float
    positions_count: int
    captured_at: datetime

    class Config:
        from_attributes = True

class MetaApiStatusResponse(BaseModel):
    id: str
    connectionStatus: str
    deploymentStatus: str
    state: Optional[str] = None
    connection_status: Optional[str] = None
    deployment_status: Optional[str] = None
    connected: bool = False

class ReconciliationSettingsBase(BaseModel):
    auto_close_orphan_positions: bool = True
    orphan_auto_close_loss_limit: float = -2.00
    orphan_auto_close_profit_enabled: bool = True
    max_minutes_orphan: int = 60
    lot_tolerance: float = 0.01
    strict_symbol_match: bool = True
    price_tolerance_points: int = 50

class ReconciliationSettingsResponse(ReconciliationSettingsBase):
    id: UUID
    updated_at: datetime

    class Config:
        from_attributes = True

class PositionReconciliationEventResponse(BaseModel):
    id: UUID
    account_id: UUID
    user_id: Optional[UUID] = None
    master_account_id: Optional[UUID] = None
    subscriber_account_id: Optional[UUID] = None
    symbol: str
    position_id: str
    side: str
    volume: float
    open_price: float
    current_price: float
    profit: float
    status: str
    reason: Optional[str] = None
    action_taken: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
