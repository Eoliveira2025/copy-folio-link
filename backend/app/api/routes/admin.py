"""Admin endpoints: full user management, strategy unlock, engine control, dashboard."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_

from app.core.database import get_db
from app.core.security import hash_password
from app.api.deps import require_admin
from app.models.user import User
from app.models.mt5_account import MT5Account, MT5Status
from app.models.strategy import Strategy, UserStrategy, MasterAccount, LOCKED_STRATEGIES
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.services import copy_engine
from app.services.payments import get_gateway, GatewayStatus

router = APIRouter()


@router.get("/dashboard")
async def admin_dashboard(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    total = await db.execute(select(func.count(User.id)))
    active_subs = await db.execute(
        select(func.count(Subscription.id)).where(Subscription.status == SubscriptionStatus.ACTIVE)
    )
    trial_subs = await db.execute(
        select(func.count(Subscription.id)).where(Subscription.status == SubscriptionStatus.TRIAL)
    )
    blocked_subs = await db.execute(
        select(func.count(Subscription.id)).where(Subscription.status == SubscriptionStatus.BLOCKED)
    )
    pending_inv = await db.execute(
        select(func.count(Invoice.id)).where(Invoice.status == InvoiceStatus.PENDING)
    )
    revenue = await db.execute(
        select(func.coalesce(func.sum(Invoice.amount), 0.0)).where(Invoice.status == InvoiceStatus.PAID)
    )

    return {
        "total_users": total.scalar() or 0,
        "active_accounts": active_subs.scalar() or 0,
        "trial_accounts": trial_subs.scalar() or 0,
        "blocked_accounts": blocked_subs.scalar() or 0,
        "pending_invoices": pending_inv.scalar() or 0,
        "total_revenue": float(revenue.scalar() or 0),
    }


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
            "created_at": u.created_at.isoformat(),
            "mt5_accounts": [
                {"id": str(m.id), "login": m.login, "server": m.server, "status": m.status.value}
                for m in mt5s
            ],
            "subscription_status": sub.status.value if sub else None,
            "active_strategy": str(active_strategy.strategy_id) if active_strategy else None,
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


@router.post("/users/{user_id}/disconnect-mt5/{account_id}")
async def admin_disconnect_mt5(
    user_id: str,
    account_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MT5Account).where(MT5Account.id == account_id, MT5Account.user_id == user_id)
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    try:
        copy_engine.dispatch_disconnect_terminal(str(account.id), account.login)
    except Exception:
        pass

    account.status = MT5Status.DISCONNECTED
    await db.commit()
    return {"message": f"MT5 account {account.login} disconnected"}


@router.post("/users/{user_id}/unblock")
async def unblock_user(
    user_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    # Unblock MT5 accounts
    mt5_result = await db.execute(
        select(MT5Account).where(MT5Account.user_id == user_id, MT5Account.status == MT5Status.BLOCKED)
    )
    for account in mt5_result.scalars().all():
        account.status = MT5Status.CONNECTED

        # Get strategy for reconnection
        us_result = await db.execute(
            select(UserStrategy).where(UserStrategy.user_id == user_id, UserStrategy.is_active == True)
        )
        active_us = us_result.scalar_one_or_none()
        if active_us:
            strat = await db.execute(select(Strategy).where(Strategy.id == active_us.strategy_id))
            strategy = strat.scalar_one_or_none()
            if strategy:
                ma = await db.execute(select(MasterAccount).where(MasterAccount.strategy_id == strategy.id))
                master = ma.scalar_one_or_none()
                if master:
                    try:
                        copy_engine.dispatch_unblock_account(
                            account_id=str(account.id),
                            login=account.login,
                            encrypted_password=account.encrypted_password,
                            server=account.server,
                            strategy_level=strategy.level.value,
                            master_login=master.login,
                            risk_multiplier=strategy.risk_multiplier,
                        )
                    except Exception:
                        pass

    # Reactivate subscription
    sub_result = await db.execute(
        select(Subscription).where(Subscription.user_id == user_id).order_by(Subscription.created_at.desc())
    )
    sub = sub_result.scalar_one_or_none()
    if sub:
        sub.status = SubscriptionStatus.ACTIVE

    await db.commit()
    return {"message": "User unblocked"}


@router.post("/check-payments")
async def check_payments_now(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Manually query all payment gateways for pending invoice status."""
    pending = await db.execute(
        select(Invoice).where(
            Invoice.status == InvoiceStatus.PENDING,
            Invoice.external_id.isnot(None),
            Invoice.provider.isnot(None),
        )
    )
    checked = 0
    paid = 0

    for invoice in pending.scalars().all():
        try:
            gateway = get_gateway(invoice.provider.value)
            result = await gateway.check_status(invoice.external_id)
            checked += 1

            if result.status == GatewayStatus.PAID:
                invoice.status = InvoiceStatus.PAID
                from datetime import datetime, timezone
                invoice.paid_at = datetime.now(timezone.utc)
                paid += 1

                # Reactivate if blocked
                sub = await db.execute(select(Subscription).where(Subscription.id == invoice.subscription_id))
                subscription = sub.scalar_one_or_none()
                if subscription and subscription.status == SubscriptionStatus.BLOCKED:
                    subscription.status = SubscriptionStatus.ACTIVE
        except Exception:
            pass

    await db.commit()
    return {"message": f"Checked {checked} invoices, {paid} newly paid"}


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
