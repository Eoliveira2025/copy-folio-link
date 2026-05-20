from pydantic import BaseModel, EmailStr
from uuid import UUID
from datetime import datetime
from typing import List, Optional
from enum import Enum

class CommissionBase(str, Enum):
    COMPANY_COMMISSION = "COMPANY_COMMISSION"
    GROSS_PROFIT = "GROSS_PROFIT"

class CommissionStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    PAID = "PAID"
    CANCELLED = "CANCELLED"

class AffiliateCreate(BaseModel):
    name: str
    email: EmailStr
    commission_percentage: float = 20.0
    commission_base: CommissionBase = CommissionBase.COMPANY_COMMISSION

class AffiliateUpdate(BaseModel):
    name: Optional[str] = None
    commission_percentage: Optional[float] = None
    commission_base: Optional[CommissionBase] = None
    active: Optional[bool] = None

class AffiliateResponse(BaseModel):
    id: UUID
    user_id: Optional[UUID]
    name: str
    email: str
    commission_percentage: float
    commission_base: CommissionBase
    active: bool
    must_change_password: bool
    created_at: datetime
    
    total_referrals: Optional[int] = 0
    pending_commission: Optional[float] = 0.0
    paid_commission: Optional[float] = 0.0

    class Config:
        from_attributes = True

class AssignReferralRequest(BaseModel):
    affiliate_id: UUID
    user_id: UUID

class AffiliateDashboardUser(BaseModel):
    user_id: UUID
    email: str
    mt5_login: Optional[int]
    strategy_name: Optional[str]
    balance: Optional[float]
    weekly_profit: Optional[float]
    affiliate_commission: Optional[float]
    commission_status: Optional[str]

class AffiliateDashboard(BaseModel):
    total_pending: float
    total_paid: float
    active_referrals_count: int
    referrals: List[AffiliateDashboardUser]
    recent_commissions: List[dict]
