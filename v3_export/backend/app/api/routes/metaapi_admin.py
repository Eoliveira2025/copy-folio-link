from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from uuid import UUID
import logging

from app.core.database import get_db
from app.api.deps import require_admin
from app.services.metaapi.service import MetaApiService
from app.services.metaapi.institutional import (
    MetaApiAccountSyncService, CopyFactoryStrategyService, 
    CopyFactorySubscriptionService, StrategySwitchService, V3HealthMonitor
)
from app.models.metaapi import MetaApiAccount, CopyFactoryStrategy, CopyFactorySubscription, StrategySwitchRequest, MetaApiEvent
from app.schemas.metaapi import (
    MetaApiAccountCreate, MetaApiAccountResponse, 
    CopyFactoryStrategyCreate, CopyFactoryStrategyResponse,
    CopyFactorySubscriptionCreate, CopyFactorySubscriptionResponse,
    StrategySwitchRequestResponse, MetaApiAccountMetricResponse
)
from app.core.config import get_settings

router = APIRouter()
settings = get_settings()
logger = logging.getLogger(__name__)

def check_v3_admin():
    if not settings.V3_ADMIN_ENABLED:
        raise HTTPException(status_code=400, detail="MetaApi V3 Admin is not enabled")

# Accounts
@router.get("/accounts", response_model=List[MetaApiAccountResponse])
async def list_accounts(
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    check_v3_admin()
    stmt = select(MetaApiAccount).order_by(MetaApiAccount.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()

@router.get("/accounts/{id}/metrics", response_model=List[MetaApiAccountMetricResponse])
async def get_account_metrics(
    id: UUID,
    limit: int = 20,
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    check_v3_admin()
    from app.models.metaapi import MetaApiAccountMetric
    stmt = select(MetaApiAccountMetric).where(MetaApiAccountMetric.account_id == id).order_by(MetaApiAccountMetric.captured_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.get("/accounts/{id}/positions")
async def get_account_positions(
    id: UUID,
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    check_v3_admin()
    stmt = select(MetaApiAccount).where(MetaApiAccount.id == id)
    account = (await db.execute(stmt)).scalars().first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return {"positions": account.last_positions_json or []}

@router.post("/accounts/{id}/sync")
async def sync_account(
    id: UUID,
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    check_v3_admin()
    stmt = select(MetaApiAccount).where(MetaApiAccount.id == id)
    account = (await db.execute(stmt)).scalars().first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    sync_service = MetaApiAccountSyncService(db)
    await sync_service.sync_account(account)
    return {"status": "SUCCESS", "last_balance": account.last_balance}

# Strategies
@router.get("/strategies", response_model=List[CopyFactoryStrategyResponse])
async def list_strategies(
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    check_v3_admin()
    stmt = select(CopyFactoryStrategy).order_by(CopyFactoryStrategy.strategy_code)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/strategies", response_model=CopyFactoryStrategyResponse)
async def create_strategy(
    data: CopyFactoryStrategyCreate,
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    check_v3_admin()
    strategy = CopyFactoryStrategy(**data.dict())
    db.add(strategy)
    await db.commit()
    await db.refresh(strategy)
    return strategy

@router.put("/strategies/{id}", response_model=CopyFactoryStrategyResponse)
async def update_strategy(
    id: UUID,
    data: CopyFactoryStrategyCreate,
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    check_v3_admin()
    strategy = await db.get(CopyFactoryStrategy, id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    for key, value in data.dict().items():
        setattr(strategy, key, value)
    
    await db.commit()
    await db.refresh(strategy)
    return strategy

@router.post("/strategies/{id}/create-provider")
async def create_strategy_provider(
    id: UUID,
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    check_v3_admin()
    strategy = await db.get(CopyFactoryStrategy, id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    cf_service = CopyFactoryStrategyService(db)
    try:
        updated_strategy = await cf_service.create_or_update_provider(strategy)
        return {"status": "SUCCESS", "copyfactory_strategy_id": updated_strategy.copyfactory_strategy_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Subscriptions
@router.get("/subscriptions", response_model=List[CopyFactorySubscriptionResponse])
async def list_subscriptions(
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    check_v3_admin()
    stmt = select(CopyFactorySubscription).order_by(CopyFactorySubscription.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/subscriptions", response_model=CopyFactorySubscriptionResponse)
async def create_subscription(
    data: CopyFactorySubscriptionCreate,
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    check_v3_admin()
    # In a real admin dashboard, we might want to specify which user this is for
    # For now we'll assume the account's user
    stmt_acc = select(MetaApiAccount).where(MetaApiAccount.id == data.client_account_id)
    account = (await db.execute(stmt_acc)).scalars().first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    sub_service = CopyFactorySubscriptionService(db)
    try:
        return await sub_service.subscribe_client(
            account.user_id, 
            data.client_account_id, 
            data.strategy_id, 
            data.risk_ratio
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Switch Requests
@router.get("/switch-requests", response_model=List[StrategySwitchRequestResponse])
async def list_switch_requests(
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    check_v3_admin()
    stmt = select(StrategySwitchRequest).order_by(StrategySwitchRequest.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/switch-requests/{id}/force")
async def force_switch(
    id: UUID,
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    check_v3_admin()
    req = await db.get(StrategySwitchRequest, id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    
    # Force switch logic
    stmt_sub = select(CopyFactorySubscription).where(CopyFactorySubscription.user_id == req.user_id)
    sub = (await db.execute(stmt_sub)).scalars().first()
    
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
        
    sub_service = CopyFactorySubscriptionService(db)
    try:
        await sub_service.subscribe_client(
            req.user_id, 
            sub.client_account_id, 
            req.target_strategy_id, 
            sub.risk_ratio
        )
        sub.strategy_id = req.target_strategy_id
        req.status = "FORCED"
        req.forced_by = admin.id
        req.switched_at = datetime.utcnow()
        await db.commit()
        return {"status": "FORCED_SUCCESS"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sync-all")
async def sync_all(
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    check_v3_admin()
    sync_service = MetaApiAccountSyncService(db)
    await sync_service.sync_all_accounts()
    return {"status": "SYNC_TRIGGERED"}

@router.get("/health")
async def get_health(
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    monitor = V3HealthMonitor(db)
    return await monitor.check_health()
