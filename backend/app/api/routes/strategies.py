"""Strategy listing and selection with plan-based validation and Copy Engine auto-subscription."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.mt5_account import MT5Account, MT5Status
from app.models.strategy import Strategy, UserStrategy, MasterAccount, LOCKED_STRATEGIES, StrategyLevel
from app.models.subscription import Subscription
from app.models.plan import Plan
from app.models.upgrade_request import UpgradeRequest, UpgradeRequestStatus
from app.schemas.strategy import StrategyResponse, SelectStrategyRequest, RequestStrategyRequest
from app.services import copy_engine

router = APIRouter()


async def _get_user_allowed_strategies(user_id, db: AsyncSession) -> set[str] | None:
    """Return set of allowed strategy levels from the user's active plan, or None if no plan."""
    sub_result = await db.execute(
        select(Subscription)
        .options(selectinload(Subscription.plan))
        .where(Subscription.user_id == user_id)
        .order_by(Subscription.created_at.desc())
    )
    subscription = sub_result.scalar_one_or_none()
    if subscription and subscription.plan:
        return set(subscription.plan.allowed_strategies)
    return None


async def _get_user_balance(user_id, db: AsyncSession) -> float:
    """Get total balance from user's connected MT5 accounts."""
    result = await db.execute(
        select(MT5Account).where(
            MT5Account.user_id == user_id,
            MT5Account.status == MT5Status.CONNECTED,
        )
    )
    accounts = result.scalars().all()
    return sum(a.balance or 0 for a in accounts)


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

    # Get user's active strategy
    active_result = await db.execute(
        select(UserStrategy.strategy_id).where(
            UserStrategy.user_id == user.id, UserStrategy.is_active == True
        )
    )
    active_row = active_result.first()
    active_strategy_id = active_row[0] if active_row else None

    allowed = await _get_user_allowed_strategies(user.id, db)
    user_balance = await _get_user_balance(user.id, db)

    # Check for pending strategy requests
    pending_requests = await db.execute(
        select(UpgradeRequest.target_plan_id).where(
            UpgradeRequest.user_id == user.id,
            UpgradeRequest.status == UpgradeRequestStatus.PENDING,
        )
    )
    # We'll use a simpler approach - check pending strategy upgrade requests
    # stored via the new request endpoint

    response = []
    for s in strategies:
        # Available if: (not locked OR admin-unlocked) AND (no plan constraint OR in plan's allowed list)
        base_available = s.level not in LOCKED_STRATEGIES or s.id in unlocked_ids
        plan_available = allowed is None or s.level.value in allowed
        is_available = base_available and plan_available

        # Determine user_status
        if active_strategy_id and s.id == active_strategy_id:
            user_status = "active"
        elif is_available:
            user_status = "available"
        elif s.level in LOCKED_STRATEGIES and s.id not in unlocked_ids:
            if float(s.min_capital) > 0 and user_balance < float(s.min_capital):
                user_status = "insufficient"
            else:
                user_status = "request"
        elif float(s.min_capital) > 0 and user_balance < float(s.min_capital):
            user_status = "insufficient"
        else:
            user_status = "request"

        resp = StrategyResponse.model_validate(s)
        resp.is_available = is_available
        resp.user_status = user_status
        resp.min_capital = float(s.min_capital)
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

    # Plan-based validation
    allowed = await _get_user_allowed_strategies(user.id, db)
    if allowed is not None and strategy.level.value not in allowed:
        raise HTTPException(status_code=403, detail="Your plan does not include this strategy. Please upgrade.")

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


@router.post("/request")
async def request_strategy(
    body: RequestStrategyRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Request access to a locked/higher strategy. Admin must approve."""
    result = await db.execute(select(Strategy).where(Strategy.id == body.strategy_id))
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    # Check min capital
    user_balance = await _get_user_balance(user.id, db)
    if float(strategy.min_capital) > 0 and user_balance < float(strategy.min_capital):
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient balance. Minimum required: R$ {float(strategy.min_capital):,.2f}. Your balance: R$ {user_balance:,.2f}"
        )

    # Check if already has pending request for this strategy
    # We reuse UpgradeRequest model but with strategy context
    from app.models.upgrade_request import UpgradeRequest, UpgradeRequestStatus
    pending = await db.execute(
        select(UpgradeRequest).where(
            UpgradeRequest.user_id == user.id,
            UpgradeRequest.status == UpgradeRequestStatus.PENDING,
        )
    )
    if pending.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="You already have a pending request. Please wait for admin approval.")

    # Get current subscription info
    sub_result = await db.execute(
        select(Subscription).where(Subscription.user_id == user.id).order_by(Subscription.created_at.desc())
    )
    sub = sub_result.scalar_one_or_none()

    # Create upgrade request
    upgrade_req = UpgradeRequest(
        user_id=user.id,
        current_plan_id=sub.plan_id if sub else None,
        target_plan_id=sub.plan_id if sub else None,  # Same plan, just strategy change
        mt5_balance=user_balance,
        admin_note=f"Strategy request: {strategy.level.value.upper()} ({strategy.name})",
    )
    db.add(upgrade_req)
    await db.commit()

    return {"message": f"Request for strategy '{strategy.name}' submitted. Awaiting admin approval."}
