from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_
from typing import List, Dict, Any, Optional
from uuid import UUID
import logging
import httpx
from datetime import datetime, timezone

from app.core.database import get_db
from app.api.deps import get_current_user, require_admin
from app.models.user import User
from app.models.metaapi import (
    MetaApiAccount, CopyFactoryStrategy, CopyFactorySubscription, MetaApiMonitorEvent
)
from app.services.metaapi.institutional import V3HealthMonitor
from app.schemas.metaapi import (
    MetaApiAccountResponse, CopyFactorySubscriptionResponse
)
from app.core.config import get_settings

router = APIRouter()
settings = get_settings()
logger = logging.getLogger(__name__)

# Base URL for the isolated metaapi-service
METAAPI_SERVICE_URL = "http://ct-metaapi-service:8010"

def check_v3_enabled():
    if not settings.V3_COPY_ENABLED:
        raise HTTPException(status_code=400, detail="MetaApi V3 is not enabled")

@router.get("/me/account", response_model=Optional[MetaApiAccountResponse])
async def get_my_v3_account(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Busca a conta CLIENT do usuário logado.
    Prioriza conta com subscription ACTIVE.
    """
    check_v3_enabled()
    
    # Busca conta com assinatura ativa primeiro
    stmt = (
        select(MetaApiAccount)
        .join(CopyFactorySubscription, MetaApiAccount.id == CopyFactorySubscription.client_account_id)
        .where(
            MetaApiAccount.user_id == current_user.id,
            CopyFactorySubscription.status == "ACTIVE"
        )
    )
    account = (await db.execute(stmt)).scalars().first()
    
    if not account:
        # Fallback: última conta conectada/deployada
        stmt = (
            select(MetaApiAccount)
            .where(
                MetaApiAccount.user_id == current_user.id,
                MetaApiAccount.account_type == "CLIENT"
            )
            .order_by(MetaApiAccount.updated_at.desc())
        )
        account = (await db.execute(stmt)).scalars().first()
    
    return account

@router.get("/me/subscription")
async def get_my_v3_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Busca assinatura ACTIVE do usuário logado.
    """
    check_v3_enabled()
    
    stmt = (
        select(
            CopyFactorySubscription.id.label("subscription_id"),
            CopyFactorySubscription.status,
            CopyFactorySubscription.risk_ratio,
            MetaApiAccount.login,
            MetaApiAccount.server,
            MetaApiAccount.last_balance,
            MetaApiAccount.last_equity,
            CopyFactoryStrategy.strategy_code,
            CopyFactoryStrategy.display_name,
            CopyFactoryStrategy.copyfactory_strategy_id,
            CopyFactoryStrategy.min_balance
        )
        .join(MetaApiAccount, CopyFactorySubscription.client_account_id == MetaApiAccount.id)
        .join(CopyFactoryStrategy, CopyFactorySubscription.strategy_id == CopyFactoryStrategy.id)
        .where(
            CopyFactorySubscription.user_id == current_user.id,
            CopyFactorySubscription.status == "ACTIVE"
        )
    )
    result = await db.execute(stmt)
    row = result.first()
    
    if not row:
        return None
        
    return dict(row._mapping)

@router.get("/me/allowed-strategies")
async def get_allowed_strategies(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Calcula estratégias permitidas com base no saldo.
    """
    check_v3_enabled()
    
    # Busca a conta para pegar o saldo
    stmt = select(MetaApiAccount).where(
        MetaApiAccount.user_id == current_user.id,
        MetaApiAccount.account_type == "CLIENT"
    ).order_by(MetaApiAccount.updated_at.desc())
    account = (await db.execute(stmt)).scalars().first()
    
    balance = account.last_balance if account else 0.0
    
    # Busca todas as estratégias ativas
    stmt = select(CopyFactoryStrategy).where(CopyFactoryStrategy.is_active == True)
    strategies = (await db.execute(stmt)).scalars().all()
    
    allowed_list = []
    for s in strategies:
        allowed = balance >= s.min_balance
        allowed_list.append({
            "strategy_code": s.strategy_code,
            "display_name": s.display_name,
            "min_balance": s.min_balance,
            "copyfactory_strategy_id": s.copyfactory_strategy_id,
            "allowed": allowed,
            "reason": None if allowed else f"Saldo mínimo necessário: ${s.min_balance}"
        })
    
    return allowed_list

@router.post("/me/import-existing")
async def import_existing_account(
    login: str = Body(..., embed=True),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Importa conta existente via metaapi-service.
    """
    check_v3_enabled()
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{METAAPI_SERVICE_URL}/internal/metaapi/client/import-existing",
                json={"user_id": str(current_user.id), "login": login}
            )
            resp.raise_for_status()
            import_data = resp.json()
            
        # Puxa dados atualizados do banco local após importação bem sucedida no serviço
        stmt = select(MetaApiAccount).where(MetaApiAccount.login == login)
        account = (await db.execute(stmt)).scalars().first()
        
        # Puxa estratégias permitidas
        allowed = await get_allowed_strategies(current_user, db)
        
        return {
            "account": account,
            "allowed_strategies": allowed
        }
    except Exception as e:
        logger.error(f"Error importing account {login}: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao importar conta: {str(e)}")

@router.post("/admin/mark-provisioned")
async def admin_mark_provisioned(
    payload: Dict[str, Any],
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Marca conta como provisionada manualmente.
    """
    user_id = payload.get("user_id")
    login = payload.get("login")
    strategy_code = payload.get("strategy_code")
    cf_sub_id = payload.get("copyfactory_subscription_id")
    
    if not all([user_id, login, strategy_code]):
        raise HTTPException(status_code=400, detail="Missing required fields")
        
    # 1. Importa/Atualiza conta via service
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{METAAPI_SERVICE_URL}/internal/metaapi/client/import-existing",
                json={"user_id": user_id, "login": login}
            )
            resp.raise_for_status()
    except Exception as e:
        logger.error(f"Error updating account in mark-provisioned: {e}")
        # Prossegue mesmo se falhar a chamada HTTP para permitir ajuste manual no banco se a conta já existir
    
    # 2. Busca IDs no banco local
    stmt_acc = select(MetaApiAccount).where(MetaApiAccount.login == login)
    account = (await db.execute(stmt_acc)).scalars().first()
    if not account:
        raise HTTPException(status_code=404, detail=f"Conta {login} não encontrada no banco local")
        
    stmt_strat = select(CopyFactoryStrategy).where(CopyFactoryStrategy.strategy_code == strategy_code)
    strategy = (await db.execute(stmt_strat)).scalars().first()
    if not strategy:
        raise HTTPException(status_code=404, detail=f"Estratégia {strategy_code} não encontrada")
        
    # 3. Cancela assinaturas anteriores ACTIVE
    await db.execute(
        update(CopyFactorySubscription)
        .where(
            and_(
                CopyFactorySubscription.user_id == UUID(user_id),
                CopyFactorySubscription.status == "ACTIVE"
            )
        )
        .values(status="CANCELLED", updated_at=datetime.now(timezone.utc))
    )
    
    # 4. Cria ou atualiza assinatura para ACTIVE
    stmt_sub = select(CopyFactorySubscription).where(
        and_(
            CopyFactorySubscription.client_account_id == account.id,
            CopyFactorySubscription.strategy_id == strategy.id
        )
    )
    existing_sub = (await db.execute(stmt_sub)).scalars().first()
    
    if existing_sub:
        existing_sub.status = "ACTIVE"
        existing_sub.copyfactory_subscription_id = cf_sub_id or existing_sub.copyfactory_subscription_id
        existing_sub.risk_ratio = 1.0
        existing_sub.updated_at = datetime.now(timezone.utc)
    else:
        new_sub = CopyFactorySubscription(
            user_id=UUID(user_id),
            client_account_id=account.id,
            strategy_id=strategy.id,
            copyfactory_subscription_id=cf_sub_id,
            status="ACTIVE",
            risk_ratio=1.0
        )
        db.add(new_sub)
        
    await db.commit()
    return {"status": "SUCCESS", "message": f"Conta {login} provisionada com estratégia {strategy_code}"}

@router.get("/admin/health")
async def get_v3_health(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Detailed health check for V3 components.
    """
    monitor = V3HealthMonitor(db)
    return await monitor.check_health()

@router.get("/admin/events")
async def get_v3_monitor_events(
    severity: Optional[str] = None,
    limit: int = 50,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get recent monitoring events.
    """
    stmt = select(MetaApiMonitorEvent).order_by(MetaApiMonitorEvent.created_at.desc()).limit(limit)
    if severity:
        stmt = stmt.where(MetaApiMonitorEvent.severity == severity)
    
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/admin/monitor/scan")
async def trigger_monitor_scan(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Trigger a full monitor scan manually.
    """
    monitor = V3HealthMonitor(db)
    return await monitor.run_full_scan()
