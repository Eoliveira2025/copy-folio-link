from fastapi import APIRouter, Depends, HTTPException
from app.api.deps import get_current_active_admin
from app.services.metaapi.client import MetaApiClient
from app.services.metaapi.copyfactory import CopyFactoryService
from app.core.config import get_settings

router = APIRouter()
settings = get_settings()

@router.get("/status")
async def get_metaapi_status(admin=Depends(get_current_active_admin)):
    """Check MetaApi integration status."""
    return {
        "enabled": settings.METAAPI_ENABLED,
        "copyfactory_enabled": settings.COPYFACTORY_ENABLED,
        "region": settings.METAAPI_REGION
    }

@router.get("/accounts")
async def list_metaapi_accounts(admin=Depends(get_current_active_admin)):
    """List all accounts managed via MetaApi."""
    # Placeholder for database query
    return []

@router.post("/sync-all")
async def sync_all_metaapi(admin=Depends(get_current_active_admin)):
    """Trigger a global synchronization with MetaApi/CopyFactory."""
    if not settings.METAAPI_ENABLED:
        raise HTTPException(status_code=400, detail="MetaApi is not enabled")
    return {"status": "SYNC_TRIGGERED"}
