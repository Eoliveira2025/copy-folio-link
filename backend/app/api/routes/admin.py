"""Admin endpoints: user management, strategy unlock, server config."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from app.core.database import get_db
from app.core.security import hash_password
from app.api.deps import require_admin
from app.models.user import User
from app.models.mt5_account import MT5Account, MT5Status
from app.models.strategy import Strategy, UserStrategy, LOCKED_STRATEGIES
from app.models.subscription import Subscription
from app.models.invoice import Invoice

router = APIRouter()


@router.get("/users")
async def search_users(
    q: str = Query("", description="Search by email or MT5 login"),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    query = select(User)
    if q:
        query = query.outerjoin(MT5Account).where(
            or_(User.email.ilike(f"%{q}%"), MT5Account.login == int(q) if q.isdigit() else False)
        )
    result = await db.execute(query.limit(50))
    users = result.scalars().unique().all()

    response = []
    for u in users:
        # Fetch related data
        mt5_result = await db.execute(select(MT5Account).where(MT5Account.user_id == u.id))
        mt5s = mt5_result.scalars().all()

        sub_result = await db.execute(
            select(Subscription).where(Subscription.user_id == u.id).order_by(Subscription.created_at.desc())
        )
        sub = sub_result.scalar_one_or_none()

        strategy_result = await db.execute(
            select(UserStrategy).where(UserStrategy.user_id == u.id, UserStrategy.is_active == True)
        )
        active_strategy = strategy_result.scalar_one_or_none()

        response.append({
            "id": str(u.id),
            "email": u.email,
            "is_active": u.is_active,
            "mt5_accounts": [{"login": m.login, "server": m.server, "status": m.status.value} for m in mt5s],
            "subscription_status": sub.status.value if sub else None,
            "active_strategy": active_strategy.strategy_id if active_strategy else None,
        })
    return response


@router.post("/users/{user_id}/unlock-strategy/{strategy_id}")
async def unlock_strategy(
    user_id: str,
    strategy_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Strategy).where(Strategy.id == strategy_id))
    strategy = result.scalar_one_or_none()
    if not strategy or strategy.level not in LOCKED_STRATEGIES:
        raise HTTPException(status_code=400, detail="Strategy not found or doesn't require unlock")

    existing = await db.execute(
        select(UserStrategy).where(UserStrategy.user_id == user_id, UserStrategy.strategy_id == strategy_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Already unlocked")

    db.add(UserStrategy(user_id=user_id, strategy_id=strategy_id, unlocked_by_admin=True, is_active=False))
    await db.commit()
    return {"message": "Strategy unlocked"}


@router.post("/users/{user_id}/reset-password")
async def admin_reset_password(
    user_id: str,
    new_password: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.hashed_password = hash_password(new_password)
    await db.commit()
    return {"message": "Password reset"}


@router.post("/users/{user_id}/unblock")
async def unblock_user(
    user_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    # Unblock MT5 accounts
    result = await db.execute(
        select(MT5Account).where(MT5Account.user_id == user_id, MT5Account.status == MT5Status.BLOCKED)
    )
    for account in result.scalars().all():
        account.status = MT5Status.CONNECTED
        # TODO: notify Copy Engine to reconnect

    # Reactivate subscription
    sub_result = await db.execute(
        select(Subscription).where(Subscription.user_id == user_id).order_by(Subscription.created_at.desc())
    )
    sub = sub_result.scalar_one_or_none()
    if sub:
        sub.status = "active"

    await db.commit()
    return {"message": "User unblocked"}


@router.post("/check-payments")
async def check_payments_now(admin: User = Depends(require_admin)):
    """Trigger manual payment synchronization with all gateways."""
    # TODO: dispatch Celery task to check all pending invoices
    return {"message": "Payment check dispatched"}


@router.get("/users/{user_id}/invoices")
async def user_payment_history(
    user_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Invoice)
        .join(Subscription)
        .where(Subscription.user_id == user_id)
        .order_by(Invoice.issue_date.desc())
    )
    invoices = result.scalars().all()
    return [
        {
            "id": str(i.id),
            "amount": i.amount,
            "currency": i.currency,
            "status": i.status.value,
            "issue_date": i.issue_date.isoformat(),
            "due_date": i.due_date.isoformat(),
            "paid_at": i.paid_at.isoformat() if i.paid_at else None,
        }
        for i in invoices
    ]
