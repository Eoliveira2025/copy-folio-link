from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from app.core.database import get_db
from app.api.deps import get_current_user
from app.services.affiliate_service import AffiliateService
from app.services.affiliate_commission_service import AffiliateCommissionService
from app.models.user import UserRole
from app.models.affiliate import Affiliate
from app.schemas.affiliate import AffiliateDashboard, AffiliateCommissionResponse

router = APIRouter(prefix="/v1/affiliate", tags=["affiliate"])

async def require_affiliate(user=Depends(get_current_user)):
    user_role = getattr(user, "role", None)
    if user_role and getattr(user_role, "role", None) == UserRole.AFFILIATE:
        return user
    raise HTTPException(status_code=403, detail="Affiliate access required")

@router.get("/dashboard", response_model=AffiliateDashboard)
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    affiliate=Depends(require_affiliate)
):
    """Get affiliate dashboard data."""
    return await AffiliateService.get_affiliate_dashboard(db, affiliate.id)

@router.get("/my-commissions", response_model=List[AffiliateCommissionResponse])
async def get_my_commissions(
    db: AsyncSession = Depends(get_db),
    affiliate=Depends(require_affiliate)
):
    """Get current affiliate's commissions."""
    # Find affiliate profile for this user
    stmt = select(Affiliate).where(Affiliate.user_id == affiliate.id)
    aff_profile = (await db.execute(stmt)).scalar_one_or_none()
    
    if not aff_profile:
        raise HTTPException(status_code=403, detail="User is not an affiliate")
        
    return await AffiliateCommissionService.list_commissions_admin(
        db, affiliate_id=aff_profile.id
    )
