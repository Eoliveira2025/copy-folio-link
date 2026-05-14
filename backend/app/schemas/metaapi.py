from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional, Any

class MetaApiAccountBase(BaseModel):
    login: str
    server: str
    broker: Optional[str] = None
    region: str = "new-york"

class MetaApiAccountCreate(MetaApiAccountBase):
    password: str

class MetaApiAccountResponse(MetaApiAccountBase):
    id: UUID
    user_id: UUID
    metaapi_account_id: Optional[str] = None
    deployment_status: str
    connection_status: str
    error_message: Optional[str] = None
    last_sync_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class CopyFactorySubscriptionResponse(BaseModel):
    id: UUID
    user_id: UUID
    strategy_id: UUID
    metaapi_account_id: str
    copyfactory_strategy_id: str
    copyfactory_subscription_id: Optional[str] = None
    risk_ratio: float
    status: str
    last_sync_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True
