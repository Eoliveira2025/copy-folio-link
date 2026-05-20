from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from app.core.database import get_db
from app.api.deps import require_admin
from app.services.affiliate_service import AffiliateService
from app.services.affiliate_commission_service import AffiliateCommissionService
from app.schemas.affiliate import (
    AffiliateCreate, AffiliateUpdate, AffiliateResponse,
    AssignReferralRequest, AffiliateCommissionResponse, CommissionStatus
)
from app.models.affiliate import Affiliate

router = APIRouter(prefix="/v1/admin/affiliates", tags=["admin-affiliates"])

@router.get("/", response_model=List[AffiliateResponse])
async def list_affiliates(
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin)
):
    """List all affiliates with stats."""
    return await AffiliateService.list_affiliates(db)

@router.post("/", response_model=AffiliateResponse)
async def create_affiliate(
    body: AffiliateCreate,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin)
):
    """Create a new affiliate and its corresponding user."""
    return await AffiliateService.create_affiliate(db, body.model_dump(), admin.id)

@router.patch("/{affiliate_id}", response_model=AffiliateResponse)
async def update_affiliate(
    affiliate_id: UUID,
    body: AffiliateUpdate,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin)
):
    """Update affiliate settings."""
    from sqlalchemy import select
    result = await db.execute(select(Affiliate).where(Affiliate.id == affiliate_id))
    affiliate = result.scalar_one_or_none()
    if not affiliate:
        raise HTTPException(status_code=404, detail="Affiliate not found")
    
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(affiliate, field, value)
    
    await db.commit()
    await db.refresh(affiliate)
    return affiliate

@router.post("/{affiliate_id}/reset-password")
async def reset_affiliate_password(
    affiliate_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin)
):
    """Reset affiliate password to 'copy123' and require change."""
    success = await AffiliateService.reset_password(db, affiliate_id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to reset password")
    return {"message": "Password reset to copy123"}

@router.post("/assign-referral")
async def assign_referral(
    body: AssignReferralRequest,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin)
):
    """Assign a user to an affiliate, replacing any previous link."""
    await AffiliateService.assign_referral(db, body.affiliate_id, body.user_id, admin.id)
    return {"message": "Referral assigned successfully"}

@router.get("/{affiliate_id}/dashboard")
async def get_affiliate_admin_dashboard(
    affiliate_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin)
):
    """Get dashboard data for a specific affiliate (Admin view)."""
    from sqlalchemy import select
    result = await db.execute(select(Affiliate).where(Affiliate.id == affiliate_id))
    affiliate = result.scalar_one_or_none()
    if not affiliate:
        raise HTTPException(status_code=404, detail="Affiliate not found")
    
    return await AffiliateService.get_affiliate_dashboard(db, affiliate.user_id)

@router.get("/commissions", response_model=List[AffiliateCommissionResponse])
async def list_commissions(
    affiliate_id: Optional[UUID] = None,
    status: Optional[CommissionStatus] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin)
):
    """List all commissions with filters (Admin only)."""
    return await AffiliateCommissionService.list_commissions_admin(
        db, affiliate_id, status, date_from, date_to
    )

@router.post("/commissions/{commission_id}/approve", response_model=AffiliateCommissionResponse)
async def approve_commission(
    commission_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin)
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
    admin=Depends(require_admin)
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
    admin=Depends(require_admin)
):
    """Cancel a commission."""
    commission = await AffiliateCommissionService.update_status(db, commission_id, CommissionStatus.CANCELLED)
    if not commission:
        raise HTTPException(status_code=404, detail="Commission not found")
    return commission
