from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional, List, Literal
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
    login: str
    server: str
    name: str
    account_type: MetaApiAccountType
    metaapi_account_id: Optional[str] = None
    deployment_status: str
    connection_status: str
    created_at: datetime

    class Config:
        from_attributes = True

class MetaApiSubscriptionCreate(BaseModel):
    client_account_id: UUID
    master_account_id: UUID
    risk_ratio: float = 1.0

class MetaApiSubscriptionResponse(BaseModel):
    id: UUID
    client_account_id: UUID
    master_account_id: UUID
    copyfactory_subscription_id: Optional[str] = None
    risk_ratio: float
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class MetaApiStatusResponse(BaseModel):
    id: str
    connectionStatus: str
    deploymentStatus: str
    quoteStreamingStatus: Optional[str] = None
