from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, func
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
from app.schemas.metaapi import (
    MetaApiAccountResponse, CopyFactorySubscriptionResponse
)
from app.core.config import get_settings

router = APIRouter()
settings = get_settings()
logger = logging.getLogger(__name__)

# Base URL for the isolated metaapi-service
# In the new architecture, ct-api talks to ct-metaapi-service via HTTP
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
    Busca a conta CLIENT do usuário logado no banco local.
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
        # Fallback: última conta do tipo CLIENT
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
    Busca assinatura ACTIVE do usuário logado no banco local.
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
    Calcula estratégias permitidas com base no BALANCE (last_balance).
    """
    check_v3_enabled()
    
    # Busca a conta para pegar o saldo
    stmt = select(MetaApiAccount).where(
        MetaApiAccount.user_id == current_user.id,
        MetaApiAccount.account_type == "CLIENT"
    ).order_by(MetaApiAccount.updated_at.desc())
    account = (await db.execute(stmt)).scalars().first()
    
    # Regra V3: Sempre usar BALANCE para elegibilidade
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
    Proxy para o metaapi-service realizar a importação.
    """
    check_v3_enabled()
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Chama o serviço isolado que possui o SDK
            resp = await client.post(
                f"{METAAPI_SERVICE_URL}/internal/metaapi/client/import-existing",
                json={"user_id": str(current_user.id), "login": login}
            )
            resp.raise_for_status()
            
        # Puxa dados atualizados do banco local
        stmt = select(MetaApiAccount).where(MetaApiAccount.login == login)
        account = (await db.execute(stmt)).scalars().first()
        
        allowed = await get_allowed_strategies(current_user, db)
        
        return {
            "account": account,
            "allowed_strategies": allowed
        }
    except Exception as e:
        logger.error(f"Error importing account {login} via service: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao comunicar com serviço MetaApi: {str(e)}")

@router.post("/admin/mark-provisioned")
async def admin_mark_provisioned(
    payload: Dict[str, Any],
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Registra provisionamento manualmente no banco local.
    NÃO chama APIs externas automaticamente.
    """
    user_id = payload.get("user_id")
    login = payload.get("login")
    strategy_code = payload.get("strategy_code")
    metaapi_account_id = payload.get("metaapi_account_id") # Opcional: ID gerado no dashboard MetaApi
    cf_sub_id = payload.get("copyfactory_subscription_id") # Opcional: ID da sub no CopyFactory
    
    if not all([user_id, login, strategy_code]):
        raise HTTPException(status_code=400, detail="Missing required fields: user_id, login, strategy_code")
        
    # 1. Busca IDs no banco local
    stmt_acc = select(MetaApiAccount).where(MetaApiAccount.login == login)
    account = (await db.execute(stmt_acc)).scalars().first()
    if not account:
        raise HTTPException(status_code=404, detail=f"Conta {login} não encontrada no banco local")
    
    # Atualiza metaapi_account_id se fornecido
    if metaapi_account_id:
        account.metaapi_account_id = metaapi_account_id
        
    stmt_strat = select(CopyFactoryStrategy).where(CopyFactoryStrategy.strategy_code == strategy_code)
    strategy = (await db.execute(stmt_strat)).scalars().first()
    if not strategy:
        raise HTTPException(status_code=404, detail=f"Estratégia {strategy_code} não encontrada")
        
    # 2. Cancela assinaturas anteriores ACTIVE do usuário para garantir exclusividade
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
    
    # 3. Cria ou atualiza assinatura local para ACTIVE
    stmt_sub = select(CopyFactorySubscription).where(
        and_(
            CopyFactorySubscription.client_account_id == account.id,
            CopyFactorySubscription.strategy_id == strategy.id
        )
    )
    existing_sub = (await db.execute(stmt_sub)).scalars().first()
    
    if existing_sub:
        existing_sub.status = "ACTIVE"
        existing_sub.copyfactory_subscription_id = cf_sub_id or existing_sub.copyfactory_subscription_id or strategy.copyfactory_strategy_id
        existing_sub.updated_at = datetime.now(timezone.utc)
    else:
        new_sub = CopyFactorySubscription(
            user_id=UUID(user_id),
            client_account_id=account.id,
            strategy_id=strategy.id,
            copyfactory_subscription_id=cf_sub_id or strategy.copyfactory_strategy_id,
            status="ACTIVE",
            risk_ratio=1.0
        )
        db.add(new_sub)
        
    await db.commit()
    return {"status": "SUCCESS", "message": f"Conta {login} registrada localmente com estratégia {strategy_code}"}

@router.get("/admin/health")
async def get_v3_health(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Health check simplificado baseado no banco local.
    Resistente a quedas do serviço externo.
    """
    if not settings.V3_COPY_ENABLED:
        return {"status": "DISABLED"}
        
    try:
        # Estatísticas via Banco Local
        acc_stmt = select(
            func.count(MetaApiAccount.id).label("total"),
            func.sum(func.case((MetaApiAccount.connection_status == "CONNECTED", 1), else_=0)).label("connected"),
            func.sum(func.case((MetaApiAccount.deployment_status == "DEPLOYED", 1), else_=0)).label("deployed")
        ).where(MetaApiAccount.account_type == "CLIENT")
        
        acc_result = await db.execute(acc_stmt)
        stats = acc_result.first()
        
        sub_stmt = select(func.count(CopyFactorySubscription.id)).where(CopyFactorySubscription.status == "ACTIVE")
        sub_count = (await db.execute(sub_stmt)).scalar()
        
        return {
            "status": "OK",
            "stats": {
                "total_accounts": stats.total or 0,
                "connected": int(stats.connected or 0),
                "deployed": int(stats.deployed or 0),
                "active_subscriptions": sub_count or 0
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Error generating V3 health stats: {e}")
        return {"status": "ERROR", "message": str(e)}

@router.get("/admin/events")
async def get_v3_monitor_events(
    severity: Optional[str] = None,
    limit: int = 50,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Retorna eventos de monitoramento recentes do banco local.
    """
    stmt = select(MetaApiMonitorEvent).order_by(MetaApiMonitorEvent.created_at.desc()).limit(limit)
    if severity:
        stmt = stmt.where(MetaApiMonitorEvent.severity == severity)
    
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/admin/monitor/scan")
async def trigger_monitor_scan(
    admin: User = Depends(require_admin)
):
    """
    Aciona o scan no serviço isolado via HTTP.
    """
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{METAAPI_SERVICE_URL}/internal/monitor/scan")
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.error(f"Error triggering monitor scan: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao acionar monitor: {str(e)}")
