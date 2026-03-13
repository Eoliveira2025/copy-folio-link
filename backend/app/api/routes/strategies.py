"""Strategy listing and selection with Copy Engine auto-subscription."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.mt5_account import MT5Account, MT5Status
from app.models.strategy import Strategy, UserStrategy, MasterAccount, LOCKED_STRATEGIES
from app.schemas.strategy import StrategyResponse, SelectStrategyRequest
from app.services import copy_engine

router = APIRouter()


@router.get("/", response_model=list[StrategyResponse])
async def list_strategies(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Strategy))
    strategies = result.scalars().all()

    unlocked = await db.execute(
        select(UserStrategy.strategy_id).where(
            UserStrategy.user_id == user.id, UserStrategy.unlocked_by_admin == True
        )
    )
    unlocked_ids = {row[0] for row in unlocked.all()}

    response = []
    for s in strategies:
        is_available = s.level not in LOCKED_STRATEGIES or s.id in unlocked_ids
        resp = StrategyResponse.model_validate(s)
        resp.is_available = is_available
        response.append(resp)
    return response


@router.post("/select")
async def select_strategy(
    body: SelectStrategyRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Strategy).where(Strategy.id == body.strategy_id))
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    if strategy.level in LOCKED_STRATEGIES:
        unlocked = await db.execute(
            select(UserStrategy).where(
                UserStrategy.user_id == user.id,
                UserStrategy.strategy_id == strategy.id,
                UserStrategy.unlocked_by_admin == True,
            )
        )
        if not unlocked.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="This strategy requires admin unlock")

    # Deactivate current strategy
    current = await db.execute(
        select(UserStrategy).where(UserStrategy.user_id == user.id, UserStrategy.is_active == True)
    )
    for us in current.scalars().all():
        us.is_active = False

    # Activate new
    db.add(UserStrategy(user_id=user.id, strategy_id=strategy.id, is_active=True))

    # Get master account for new strategy
    ma_result = await db.execute(select(MasterAccount).where(MasterAccount.strategy_id == strategy.id))
    master = ma_result.scalar_one_or_none()

    # Re-subscribe all connected MT5 accounts to the new strategy
    if master:
        mt5_result = await db.execute(
            select(MT5Account).where(
                MT5Account.user_id == user.id,
                MT5Account.status == MT5Status.CONNECTED,
            )
        )
        for account in mt5_result.scalars().all():
            try:
                copy_engine.dispatch_subscribe_strategy(
                    account_id=str(account.id),
                    client_login=account.login,
                    strategy_level=strategy.level.value,
                    master_login=master.login,
                    risk_multiplier=strategy.risk_multiplier,
                )
            except Exception:
                pass

    await db.commit()
    return {"message": f"Strategy '{strategy.name}' activated"}
