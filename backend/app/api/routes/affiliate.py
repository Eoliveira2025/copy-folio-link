from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.api.deps import get_current_user
from app.services.affiliate_service import AffiliateService
from app.models.user import UserRole
from app.schemas.affiliate import AffiliateDashboard

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
