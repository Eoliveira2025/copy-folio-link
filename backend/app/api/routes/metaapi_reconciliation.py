from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel
import asyncio
import logging

from app.api import deps
from app.schemas.metaapi import (
    PositionReconciliationEventResponse, 
    ReconciliationSettingsResponse,
    ReconciliationSettingsBase
)
from app.services.metaapi.reconciliation import PositionReconciliationService
from app.models.user import User

router = APIRouter()
logger = logging.getLogger(__name__)

class ReconciliationTriggerPayload(BaseModel):
    strategy_code: Optional[str] = None
    master_account_id: Optional[str] = None
    event_type: str # POSITION_OPENED | POSITION_CLOSED
    symbol: Optional[str] = None
    position_id: Optional[str] = None

@router.get("/settings", response_model=ReconciliationSettingsResponse)
async def get_reconciliation_settings(
    db: AsyncSession = Depends(deps.get_db),
    current_admin: User = Depends(deps.require_admin)
):
    service = PositionReconciliationService(db)
    return await service.get_settings()

@router.post("/settings", response_model=ReconciliationSettingsResponse)
async def update_reconciliation_settings_post(
    settings_data: ReconciliationSettingsBase,
    db: AsyncSession = Depends(deps.get_db),
    current_admin: User = Depends(deps.require_admin)
):
    service = PositionReconciliationService(db)
    return await service.update_settings(settings_data.model_dump())

@router.patch("/settings", response_model=ReconciliationSettingsResponse)
async def update_reconciliation_settings_patch(
    settings_data: ReconciliationSettingsBase,
    db: AsyncSession = Depends(deps.get_db),
    current_admin: User = Depends(deps.require_admin)
):
    service = PositionReconciliationService(db)
    return await service.update_settings(settings_data.model_dump())

@router.get("/events", response_model=List[PositionReconciliationEventResponse])
async def list_reconciliation_events(
    status: Optional[str] = None,
    db: AsyncSession = Depends(deps.get_db),
    current_admin: User = Depends(deps.require_admin)
):
    service = PositionReconciliationService(db)
    return await service.get_events(status=status)

@router.post("/scan", status_code=202)
async def trigger_reconciliation_scan(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(deps.get_db),
    current_admin: User = Depends(deps.require_admin)
):
    """Manually trigger reconciliation process (Full Scan)."""
    service = PositionReconciliationService(db)
    background_tasks.add_task(service.detect_all_orphans)
    return {"message": "Reconciliation process (full scan) started in background"}

async def delayed_reconciliation_task(
    strategy_code: Optional[str],
    master_account_id: Optional[str],
    db_session_factory
):
    """Wait 3-5 seconds and run reconciliation."""
    delay = 5 # As requested (3 to 5 seconds)
    logger.info(f"[RECON TRIGGER] Delayed scan task started. Waiting {delay}s...")
    await asyncio.sleep(delay)
    
    async with db_session_factory() as db:
        service = PositionReconciliationService(db)
        try:
            if strategy_code:
                logger.info(f"[RECON TRIGGER] Running scan for strategy: {strategy_code}")
                await service.detect_orphans_for_strategy(strategy_code)
            elif master_account_id:
                logger.info(f"[RECON TRIGGER] Running scan for master account: {master_account_id}")
                await service.detect_orphans_for_master(UUID(master_account_id))
            else:
                logger.info("[RECON TRIGGER] Running full scan (fallback)")
                await service.detect_all_orphans()
            logger.info("[RECON TRIGGER] Delayed scan completed.")
        except Exception as e:
            logger.error(f"[RECON ERROR] Failed in delayed task: {e}")

@router.post("/trigger", status_code=202)
async def trigger_event_reconciliation(
    payload: ReconciliationTriggerPayload,
    background_tasks: BackgroundTasks,
    # This endpoint might be called by internal services, but we check admin for security if through main API
    # User requested as /api/v1/admin/metaapi/reconciliation/trigger
    current_admin: User = Depends(deps.require_admin)
):
    """
    Trigger reconciliation based on a master event (Position Opened/Closed).
    Runs with a delay to allow the copy engine to finish its work.
    """
    from app.core.database import AsyncSessionLocal
    
    logger.info(f"[RECON TRIGGER] Received event: {payload.event_type} for {payload.symbol or 'all'} (ID: {payload.position_id or 'N/A'})")
    
    background_tasks.add_task(
        delayed_reconciliation_task,
        payload.strategy_code,
        payload.master_account_id,
        AsyncSessionLocal
    )
    
    return {"status": "ACCEPTED", "message": "Reconciliation triggered with delay"}

@router.post("/events/{event_id}/approve-close", response_model=PositionReconciliationEventResponse)
async def approve_close_orphan(
    event_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_admin: User = Depends(deps.require_admin)
):
    service = PositionReconciliationService(db)
    try:
        return await service.approve_close_orphan(event_id, current_admin.id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/events/{event_id}/ignore", response_model=PositionReconciliationEventResponse)
async def ignore_orphan(
    event_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_admin: User = Depends(deps.require_admin)
):
    service = PositionReconciliationService(db)
    try:
        return await service.ignore_orphan(event_id, current_admin.id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
