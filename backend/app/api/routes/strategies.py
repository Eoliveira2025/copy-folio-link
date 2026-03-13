"""Strategy listing and selection endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.strategy import Strategy, UserStrategy, LOCKED_STRATEGIES
from app.schemas.strategy import StrategyResponse, SelectStrategyRequest

router = APIRouter()


@router.get("/", response_model=list[StrategyResponse])
async def list_strategies(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Strategy))
    strategies = result.scalars().all()

    # Check which locked strategies user has unlocked
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
    await db.commit()

    return {"message": f"Strategy '{strategy.name}' activated"}
