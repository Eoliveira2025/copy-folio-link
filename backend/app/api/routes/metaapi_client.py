from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Dict, Any
from uuid import UUID
import logging

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.metaapi import (
    MetaApiAccount, CopyFactoryStrategy, CopyFactorySubscription, 
    StrategySwitchRequest
)
from app.services.metaapi.institutional import (
    MetaApiAccountSyncService, StrategySwitchService
)
from app.schemas.metaapi import (
    MetaApiAccountResponse, StrategySwitchRequestResponse, 
    StrategySwitchRequestCreate
)
from app.core.config import get_settings

router = APIRouter()
settings = get_settings()
logger = logging.getLogger(__name__)

def check_v3_enabled():
    if not settings.V3_COPY_ENABLED:
        raise HTTPException(status_code=400, detail="MetaApi V3 is not enabled")

@router.get("/my-account/status", response_model=MetaApiAccountResponse)
async def get_my_account_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    check_v3_enabled()
    stmt = select(MetaApiAccount).where(MetaApiAccount.user_id == current_user.id)
    account = (await db.execute(stmt)).scalars().first()
    if not account:
        raise HTTPException(status_code=404, detail="MetaApi account not linked to this user")
    
    # Optional: Trigger a sync on request to show fresh data
    sync_service = MetaApiAccountSyncService(db)
    await sync_service.sync_account(account)
    
    return account

@router.get("/my-account/positions")
async def get_my_positions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    check_v3_enabled()
    stmt = select(MetaApiAccount).where(MetaApiAccount.user_id == current_user.id)
    account = (await db.execute(stmt)).scalars().first()
    if not account:
        raise HTTPException(status_code=404, detail="MetaApi account not found")
    
    return {"positions": account.last_positions_json or []}

@router.post("/my-strategy/request-switch", response_model=StrategySwitchRequestResponse)
async def request_strategy_switch(
    data: StrategySwitchRequestCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    check_v3_enabled()
    switch_service = StrategySwitchService(db)
    try:
        return await switch_service.request_switch(current_user.id, data.target_strategy_id)
    except Exception as e:
        logger.error(f"Error requesting switch for user {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/my-strategy/switch-status", response_model=List[StrategySwitchRequestResponse])
async def get_switch_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    check_v3_enabled()
    stmt = select(StrategySwitchRequest).where(StrategySwitchRequest.user_id == current_user.id).order_by(StrategySwitchRequest.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()
