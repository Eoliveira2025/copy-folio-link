"""MT5 Account connection endpoints with Copy Engine integration."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import encrypt_mt5_password
from app.api.deps import get_current_user
from app.models.user import User
from app.models.mt5_account import MT5Account, MT5Status
from app.models.strategy import Strategy, MasterAccount, UserStrategy, StrategyLevel
from app.schemas.mt5 import ConnectMT5Request, MT5AccountResponse
from app.services import copy_engine

router = APIRouter()

ALLOWED_SERVERS = [
    "Exness-MT5Real", "Exness-MT5Real2", "Exness-MT5Real3", "Exness-MT5Trial",
]


@router.post("/connect", response_model=MT5AccountResponse, status_code=status.HTTP_201_CREATED)
async def connect_mt5(
    body: ConnectMT5Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.server not in ALLOWED_SERVERS:
        raise HTTPException(status_code=400, detail=f"Server not supported. Allowed: {ALLOWED_SERVERS}")

    # Check duplicate
    existing = await db.execute(select(MT5Account).where(MT5Account.login == body.login))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="This MT5 account is already connected")

    # Check subscription is not blocked
    from app.models.subscription import Subscription, SubscriptionStatus
    sub_result = await db.execute(
        select(Subscription).where(Subscription.user_id == user.id).order_by(Subscription.created_at.desc())
    )
    sub = sub_result.scalar_one_or_none()
    if sub and sub.status == SubscriptionStatus.BLOCKED:
        raise HTTPException(status_code=403, detail="Account is blocked due to unpaid invoice. Please pay your invoice first.")

    encrypted_pass = encrypt_mt5_password(body.password)
    account = MT5Account(
        user_id=user.id,
        login=body.login,
        encrypted_password=encrypted_pass,
        server=body.server,
        status=MT5Status.CONNECTED,
    )
    db.add(account)
    await db.flush()
    await db.refresh(account)

    # ── Auto-assign LOW strategy if user has no active strategy ──
    strategy_result = await db.execute(
        select(UserStrategy).where(UserStrategy.user_id == user.id, UserStrategy.is_active == True)
    )
    active_us = strategy_result.scalar_one_or_none()

    if not active_us:
        # Find the LOW strategy
        low_result = await db.execute(
            select(Strategy).where(Strategy.level == StrategyLevel.LOW)
        )
        low_strategy = low_result.scalar_one_or_none()
        if low_strategy:
            active_us = UserStrategy(
                user_id=user.id,
                strategy_id=low_strategy.id,
                is_active=True,
            )
            db.add(active_us)
            await db.flush()

    master_login = None
    strategy_level = None
    risk_multiplier = 1.0

    if active_us:
        strat = await db.execute(select(Strategy).where(Strategy.id == active_us.strategy_id))
        strategy = strat.scalar_one_or_none()
        if strategy:
            strategy_level = strategy.level.value
            risk_multiplier = strategy.risk_multiplier
            # Get master account for this strategy
            ma_result = await db.execute(
                select(MasterAccount).where(MasterAccount.strategy_id == strategy.id)
            )
            master = ma_result.scalar_one_or_none()
            if master:
                master_login = master.login

    # Dispatch to Copy Engine via Redis
    try:
        copy_engine.dispatch_connect_terminal(
            account_id=str(account.id),
            login=body.login,
            encrypted_password=encrypted_pass,
            server=body.server,
            strategy_level=strategy_level,
            master_login=master_login,
        )

        if strategy_level and master_login:
            copy_engine.dispatch_subscribe_strategy(
                account_id=str(account.id),
                client_login=body.login,
                strategy_level=strategy_level,
                master_login=master_login,
                risk_multiplier=risk_multiplier,
            )
    except Exception as e:
        # Don't fail the connection if Redis is down, just log
        import logging
        logging.getLogger(__name__).error(f"Failed to dispatch to copy engine: {e}")

    await db.commit()
    return account


@router.get("/accounts", response_model=list[MT5AccountResponse])
async def list_accounts(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(MT5Account).where(MT5Account.user_id == user.id))
    return result.scalars().all()


@router.delete("/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_mt5(
    account_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MT5Account).where(MT5Account.id == account_id, MT5Account.user_id == user.id)
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    # Notify Copy Engine to tear down terminal
    try:
        copy_engine.dispatch_disconnect_terminal(str(account.id), account.login)
    except Exception:
        pass

    await db.delete(account)
    await db.commit()
