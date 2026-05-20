from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from uuid import UUID

from app.core.database import get_db
from app.api.deps import get_current_user
from app.schemas.affiliate import AffiliateCommissionResponse
from app.services.affiliate_commission_service import AffiliateCommissionService
from app.models.affiliate import Affiliate
from sqlalchemy import select

router = APIRouter()

@router.get("/my-commissions", response_model=List[AffiliateCommissionResponse])
async def get_my_commissions(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """Get current affiliate's commissions."""
    # Find affiliate profile for this user
    stmt = select(Affiliate).where(Affiliate.user_id == current_user.id)
    affiliate = (await db.execute(stmt)).scalar_one_or_none()
    
    if not affiliate:
        raise HTTPException(status_code=403, detail="User is not an affiliate")
        
    return await AffiliateCommissionService.list_commissions_admin(
        db, affiliate_id=affiliate.id
    )
