from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import UUID

from app.api import deps
from app.schemas.metaapi import (
    PositionReconciliationEventResponse, 
    ReconciliationSettingsResponse,
    ReconciliationSettingsBase
)
from app.services.metaapi.reconciliation import PositionReconciliationService
from app.models.user import User

router = APIRouter()

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
    """Manually trigger reconciliation process."""
    service = PositionReconciliationService(db)
    background_tasks.add_task(service.detect_all_orphans)
    return {"message": "Reconciliation process (scan) started in background"}

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
