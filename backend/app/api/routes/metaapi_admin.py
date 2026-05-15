from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from uuid import UUID
import logging
from app.core.database import get_db
from app.api.deps import require_admin
from app.services.metaapi.service import MetaApiService
from app.models.metaapi import MetaApiEvent
from app.schemas.metaapi import (
    MetaApiAccountCreate, 
    MetaApiAccountResponse, 
    MetaApiSubscriptionCreate, 
    MetaApiSubscriptionResponse,
    MetaApiStatusResponse
)
from app.core.config import get_settings

router = APIRouter()
settings = get_settings()
logger = logging.getLogger(__name__)

def check_enabled():
    if not settings.METAAPI_ENABLED:
        raise HTTPException(status_code=400, detail="MetaApi is not enabled")

@router.get("/health")
async def get_metaapi_health():
    """Health check for MetaApi integration."""
    return {
        "status": "ready",
        "version": "v3-metaapi",
        "metaapi_enabled": settings.METAAPI_ENABLED,
        "copyfactory_enabled": settings.COPYFACTORY_ENABLED,
        "region": settings.METAAPI_REGION
    }

@router.get("/status")
async def get_metaapi_status(
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Check MetaApi integration status."""
    return {
        "enabled": settings.METAAPI_ENABLED,
        "copyfactory_enabled": settings.COPYFACTORY_ENABLED,
        "region": settings.METAAPI_REGION,
        "token_configured": bool(settings.METAAPI_TOKEN)
    }

@router.post("/accounts", response_model=MetaApiAccountResponse)
async def create_metaapi_account(
    data: MetaApiAccountCreate,
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    check_enabled()
    service = MetaApiService(db)
    try:
        # Pass admin.id as user_id for system accounts
        return await service.create_and_deploy_account(admin.id, data.dict())
    except Exception as e:
        logger.error(f"Error creating account: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"MetaApi Error: {str(e)}")

@router.get("/accounts", response_model=List[MetaApiAccountResponse])
async def list_metaapi_accounts(
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    check_enabled()
    service = MetaApiService(db)
    return await service.list_accounts()

@router.post("/accounts/{id}/deploy")
async def deploy_metaapi_account(
    id: UUID,
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    check_enabled()
    service = MetaApiService(db)
    try:
        return await service.deploy_account(id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/accounts/{id}/status", response_model=MetaApiStatusResponse)
async def get_account_status(
    id: UUID,
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    check_enabled()
    service = MetaApiService(db)
    status = await service.get_account_status(id)
    if "error" in status:
        raise HTTPException(status_code=500, detail=status["error"])
    return status

@router.delete("/accounts/{id}")
async def delete_metaapi_account(
    id: UUID,
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    check_enabled()
    service = MetaApiService(db)
    return await service.remove_account(id)

@router.post("/masters/{id}/create-provider")
async def create_provider(
    id: UUID,
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    if not settings.COPYFACTORY_ENABLED:
        raise HTTPException(status_code=400, detail="CopyFactory is not enabled")
    service = MetaApiService(db)
    try:
        return await service.create_cf_provider(id)
    except Exception as e:
        logger.error(f"Error creating provider: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/subscriptions", response_model=MetaApiSubscriptionResponse)
async def create_subscription(
    data: MetaApiSubscriptionCreate,
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    if not settings.COPYFACTORY_ENABLED:
        raise HTTPException(status_code=400, detail="CopyFactory is not enabled")
    service = MetaApiService(db)
    try:
        return await service.subscribe_client(
            data.client_account_id, 
            data.master_account_id, 
            data.risk_ratio
        )
    except Exception as e:
        logger.error(f"Error creating subscription: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/subscriptions", response_model=List[MetaApiSubscriptionResponse])
async def list_subscriptions(
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    if not settings.COPYFACTORY_ENABLED:
        raise HTTPException(status_code=400, detail="CopyFactory is not enabled")
    service = MetaApiService(db)
    return await service.list_subscriptions()

@router.get("/events")
async def list_events(
    limit: int = 50,
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    check_enabled()
    stmt = select(MetaApiEvent).order_by(MetaApiEvent.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/sync-all")
async def sync_all_metaapi(
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Trigger a global synchronization with MetaApi/CopyFactory."""
    check_enabled()
    # In a real scenario, this would trigger background tasks to refresh all statuses
    return {"status": "SYNC_TRIGGERED"}
