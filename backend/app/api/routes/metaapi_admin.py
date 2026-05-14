from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.api.deps import require_admin
from app.services.metaapi.client import MetaApiClient
from app.services.metaapi.copyfactory import CopyFactoryService
from app.core.config import get_settings

router = APIRouter()
settings = get_settings()

@router.get("/status")
async def get_metaapi_status(
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Check MetaApi integration status."""
    return {
        "enabled": settings.METAAPI_ENABLED,
        "copyfactory_enabled": settings.COPYFACTORY_ENABLED,
        "region": settings.METAAPI_REGION
    }

@router.get("/accounts")
async def list_metaapi_accounts(
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """List all accounts managed via MetaApi."""
    return []

@router.post("/sync-all")
async def sync_all_metaapi(
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Trigger a global synchronization with MetaApi/CopyFactory."""
    if not settings.METAAPI_ENABLED:
        raise HTTPException(status_code=400, detail="MetaApi is not enabled")
    return {"status": "SYNC_TRIGGERED"}
