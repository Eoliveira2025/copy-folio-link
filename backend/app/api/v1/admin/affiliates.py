from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from app.core.database import get_db
from app.api.deps import get_current_admin
from app.schemas.affiliate import AffiliateCommissionResponse, CommissionStatus
from app.services.affiliate_commission_service import AffiliateCommissionService

router = APIRouter()

@router.get("/commissions", response_model=List[AffiliateCommissionResponse])
async def list_commissions(
    affiliate_id: Optional[UUID] = None,
    status: Optional[CommissionStatus] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db),
    admin=Depends(get_current_admin)
):
    """List all commissions with filters (Admin only)."""
    return await AffiliateCommissionService.list_commissions_admin(
        db, affiliate_id, status, date_from, date_to
    )

@router.post("/commissions/{commission_id}/approve", response_model=AffiliateCommissionResponse)
async def approve_commission(
    commission_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin=Depends(get_current_admin)
):
    """Approve a pending commission."""
    commission = await AffiliateCommissionService.update_status(db, commission_id, CommissionStatus.APPROVED)
    if not commission:
        raise HTTPException(status_code=404, detail="Commission not found")
    return commission

@router.post("/commissions/{commission_id}/mark-paid", response_model=AffiliateCommissionResponse)
async def mark_paid_commission(
    commission_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin=Depends(get_current_admin)
):
    """Mark a commission as paid."""
    commission = await AffiliateCommissionService.update_status(db, commission_id, CommissionStatus.PAID)
    if not commission:
        raise HTTPException(status_code=404, detail="Commission not found")
    return commission

@router.post("/commissions/{commission_id}/cancel", response_model=AffiliateCommissionResponse)
async def cancel_commission(
    commission_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin=Depends(get_current_admin)
):
    """Cancel a commission."""
    commission = await AffiliateCommissionService.update_status(db, commission_id, CommissionStatus.CANCELLED)
    if not commission:
        raise HTTPException(status_code=404, detail="Commission not found")
    return commission
