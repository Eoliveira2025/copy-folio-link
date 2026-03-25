"""MT5 Account connection endpoints — hybrid flow with PENDING_PROVISION status."""

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


def _is_allowed_server(server: str) -> bool:
    """Accept any Exness server dynamically instead of hardcoded list."""
    return server.startswith("Exness-MT5")


@router.post("/connect", response_model=MT5AccountResponse, status_code=status.HTTP_201_CREATED)
async def connect_mt5(
    body: ConnectMT5Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not _is_allowed_server(body.server):
        raise HTTPException(status_code=400, detail="Server not supported. Only Exness MT5 servers are allowed.")

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

    # Encrypt password for storage, but store in a way that admin can decrypt for manual login
    encrypted_pass = encrypt_mt5_password(body.password)

    # Status is PENDING_PROVISION — admin must do manual first login
    account = MT5Account(
        user_id=user.id,
        login=body.login,
        encrypted_password=encrypted_pass,
        server=body.server,
        status=MT5Status.PENDING_PROVISION,
    )
    db.add(account)
    await db.flush()
    await db.refresh(account)

    # Auto-assign LOW strategy if user has no active strategy
    strategy_result = await db.execute(
        select(UserStrategy).where(UserStrategy.user_id == user.id, UserStrategy.is_active == True)
    )
    active_us = strategy_result.scalar_one_or_none()

    if not active_us:
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

    await db.commit()

    import logging
    logging.getLogger(__name__).info(
        f"MT5 account {body.login} registered as PENDING_PROVISION for user {user.email}"
    )

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

    # Notify Copy Engine to tear down terminal (only if was connected)
    if account.status == MT5Status.CONNECTED:
        try:
            copy_engine.dispatch_disconnect_terminal(str(account.id), account.login)
        except Exception:
            pass

    await db.delete(account)
    await db.commit()
