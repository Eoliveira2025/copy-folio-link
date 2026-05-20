from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional, List
from app.models.performance_billing import BillingMethodType, CycleStatus

class BillingMethodBase(BaseModel):
    method: BillingMethodType
    performance_percentage: float = Field(..., ge=0, le=100)

class BillingMethodCreate(BillingMethodBase):
    user_id: UUID

class BillingMethodResponse(BillingMethodBase):
    id: UUID
    user_id: UUID
    active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class PerformanceCycleBase(BaseModel):
    user_id: UUID
    account_source: str
    account_login: str
    strategy_code: Optional[str] = None
    cycle_start: datetime
    cycle_end: Optional[datetime] = None
    start_balance: float
    end_balance: Optional[float] = None
    gross_profit: Optional[float] = None
    commission_percentage: float
    commission_amount: Optional[float] = None
    status: CycleStatus
    invoice_id: Optional[UUID] = None
    notes: Optional[str] = None

class PerformanceCycleResponse(PerformanceCycleBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class PerformanceUserSummary(BaseModel):
    user_id: UUID
    full_name: Optional[str] = None
    email: str
    method: Optional[BillingMethodType] = None
    performance_percentage: Optional[float] = None
    strategy_code: Optional[str] = None
    account_login: Optional[str] = None
    current_balance: Optional[float] = None

class PerformanceBillingDashboard(BaseModel):
    open_commissions: float
    total_invoiced: float
    profitable_cycles: int
    negative_cycles: int
