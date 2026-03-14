"""Billing endpoints with plan-aware subscription, upgrade requests, and full payment gateway integration."""

import logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

logger = logging.getLogger("app.billing")

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.plan import Plan
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.invoice import Invoice, InvoiceStatus, Payment, PaymentProvider
from app.models.mt5_account import MT5Account, MT5Status
from app.models.upgrade_request import UpgradeRequest, UpgradeRequestStatus
from app.schemas.billing import SubscriptionResponse, InvoiceResponse, UpgradeRequestCreate, UpgradeRequestResponse
from app.services.payments import get_gateway, GatewayStatus
from app.services import copy_engine

router = APIRouter()


@router.get("/plans")
async def list_available_plans(db: AsyncSession = Depends(get_db)):
    """Public endpoint listing active plans."""
    result = await db.execute(select(Plan).where(Plan.active == True).order_by(Plan.price))
    plans = result.scalars().all()
    return [
        {
            "id": str(p.id),
            "name": p.name,
            "price": p.price,
            "currency": p.currency,
            "allowed_strategies": p.allowed_strategies,
            "trial_days": p.trial_days,
            "max_accounts": p.max_accounts,
        }
        for p in plans
    ]


@router.get("/subscription")
async def get_subscription(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Subscription)
        .options(selectinload(Subscription.plan))
        .where(Subscription.user_id == user.id)
        .order_by(Subscription.created_at.desc())
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="No subscription found")

    plan_name = sub.plan.name if sub.plan else None
    plan_price = sub.plan.price if sub.plan else None

    return SubscriptionResponse(
        id=sub.id,
        status=sub.status.value,
        plan_name=plan_name,
        plan_price=plan_price,
        trial_start=sub.trial_start,
        trial_end=sub.trial_end,
        current_period_start=sub.current_period_start,
        current_period_end=sub.current_period_end,
        auto_renew=sub.auto_renew,
    )


@router.get("/invoices", response_model=list[InvoiceResponse])
async def list_invoices(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Invoice)
        .join(Subscription)
        .where(Subscription.user_id == user.id)
        .order_by(Invoice.issue_date.desc())
    )
    return result.scalars().all()


# ── Upgrade Requests ────────────────────────────────────

@router.get("/upgrade-check")
async def check_upgrade_eligibility(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Check if user's MT5 balance qualifies for a plan upgrade."""
    sub_result = await db.execute(
        select(Subscription)
        .options(selectinload(Subscription.plan))
        .where(Subscription.user_id == user.id)
        .order_by(Subscription.created_at.desc())
    )
    sub = sub_result.scalar_one_or_none()
    if not sub or not sub.plan_id:
        return {"eligible": False, "reason": "No active plan"}

    current_plan = sub.plan

    # Get MT5 balance
    mt5_result = await db.execute(select(MT5Account).where(MT5Account.user_id == user.id))
    mt5 = mt5_result.scalars().first()
    balance = mt5.balance if mt5 and mt5.balance else 0.0

    # Find next plan by price
    next_plan_result = await db.execute(
        select(Plan).where(
            Plan.active == True,
            Plan.price > (current_plan.price if current_plan else 0)
        ).order_by(Plan.price).limit(1)
    )
    next_plan = next_plan_result.scalar_one_or_none()
    if not next_plan:
        return {"eligible": False, "reason": "Already on highest plan"}

    # Check if there's a pending request already
    pending = await db.execute(
        select(UpgradeRequest).where(
            UpgradeRequest.user_id == user.id,
            UpgradeRequest.status == UpgradeRequestStatus.PENDING,
        )
    )
    has_pending = pending.scalar_one_or_none() is not None

    # Simple eligibility: balance > next plan price * 10 (configurable threshold)
    min_balance = next_plan.price * 10
    eligible = balance >= min_balance

    return {
        "eligible": eligible,
        "has_pending_request": has_pending,
        "current_plan": {"id": str(current_plan.id), "name": current_plan.name, "price": current_plan.price} if current_plan else None,
        "next_plan": {"id": str(next_plan.id), "name": next_plan.name, "price": next_plan.price},
        "mt5_balance": balance,
        "min_balance_required": min_balance,
    }


@router.post("/upgrade-request")
async def request_upgrade(
    body: UpgradeRequestCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """User requests a plan upgrade. Creates a pending request for admin approval."""
    # Check no pending request exists
    pending = await db.execute(
        select(UpgradeRequest).where(
            UpgradeRequest.user_id == user.id,
            UpgradeRequest.status == UpgradeRequestStatus.PENDING,
        )
    )
    if pending.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="You already have a pending upgrade request")

    # Validate target plan
    target_result = await db.execute(select(Plan).where(Plan.id == body.target_plan_id, Plan.active == True))
    target_plan = target_result.scalar_one_or_none()
    if not target_plan:
        raise HTTPException(status_code=404, detail="Target plan not found or inactive")

    # Get current plan
    sub_result = await db.execute(
        select(Subscription).where(Subscription.user_id == user.id).order_by(Subscription.created_at.desc())
    )
    sub = sub_result.scalar_one_or_none()
    current_plan_id = sub.plan_id if sub else None

    # Get MT5 balance
    mt5_result = await db.execute(select(MT5Account).where(MT5Account.user_id == user.id))
    mt5 = mt5_result.scalars().first()
    balance = mt5.balance if mt5 and mt5.balance else 0.0

    request = UpgradeRequest(
        user_id=user.id,
        current_plan_id=current_plan_id,
        target_plan_id=target_plan.id,
        mt5_balance=balance,
    )
    db.add(request)
    await db.commit()
    await db.refresh(request)

    return {"message": "Upgrade request submitted", "request_id": str(request.id)}


@router.get("/upgrade-requests")
async def my_upgrade_requests(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """List user's own upgrade requests."""
    result = await db.execute(
        select(UpgradeRequest).where(UpgradeRequest.user_id == user.id).order_by(UpgradeRequest.created_at.desc())
    )
    requests = result.scalars().all()
    response = []
    for r in requests:
        current_name = None
        target_name = None
        target_price = None
        if r.current_plan_id:
            cp = await db.execute(select(Plan).where(Plan.id == r.current_plan_id))
            p = cp.scalar_one_or_none()
            current_name = p.name if p else None
        if r.target_plan_id:
            tp = await db.execute(select(Plan).where(Plan.id == r.target_plan_id))
            p = tp.scalar_one_or_none()
            if p:
                target_name = p.name
                target_price = p.price
        response.append(UpgradeRequestResponse(
            id=r.id, user_id=r.user_id, current_plan_name=current_name,
            target_plan_name=target_name, target_plan_price=target_price,
            mt5_balance=r.mt5_balance, status=r.status.value,
            admin_note=r.admin_note, created_at=r.created_at, resolved_at=r.resolved_at,
        ))
    return response


async def _handle_payment_confirmation(invoice: Invoice, db: AsyncSession):
    """Shared logic for marking invoice paid, advancing billing date, and reactivating subscription."""
    invoice.status = InvoiceStatus.PAID
    invoice.paid_at = datetime.now(timezone.utc)

    sub = await db.execute(select(Subscription).where(Subscription.id == invoice.subscription_id))
    subscription = sub.scalar_one_or_none()
    if subscription:
        now = datetime.now(timezone.utc)
        cycle = subscription.billing_cycle_days or 30

        # Advance billing schedule
        subscription.current_period_start = now
        subscription.current_period_end = now + timedelta(days=cycle)
        subscription.next_billing_date = now + timedelta(days=cycle)

        if subscription.status == SubscriptionStatus.BLOCKED:
            subscription.status = SubscriptionStatus.ACTIVE

        if subscription.status == SubscriptionStatus.TRIAL:
            subscription.status = SubscriptionStatus.ACTIVE

        mt5_result = await db.execute(
            select(MT5Account).where(MT5Account.user_id == subscription.user_id)
        )
        for account in mt5_result.scalars().all():
            if account.status == MT5Status.BLOCKED:
                account.status = MT5Status.CONNECTED

                from app.models.strategy import Strategy, MasterAccount, UserStrategy
                us_result = await db.execute(
                    select(UserStrategy).where(
                        UserStrategy.user_id == subscription.user_id, UserStrategy.is_active == True
                    )
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


async def _process_gateway_webhook(provider: PaymentProvider, request: Request, db: AsyncSession):
    """Generic webhook handler for all gateways."""
    payload = await request.json()
    gateway = get_gateway(provider.value)
    result = await gateway.process_webhook(payload)

    if result.status == GatewayStatus.PAID and result.gateway_id:
        inv = await db.execute(select(Invoice).where(Invoice.external_id == result.gateway_id))
        invoice = inv.scalar_one_or_none()
        if invoice:
            # Idempotency: skip if already paid
            if invoice.status == InvoiceStatus.PAID:
                logger.info(f"Duplicate webhook ignored for invoice {invoice.id} (already paid)")
                return {"status": "ok", "note": "already_paid"}

            db.add(Payment(
                invoice_id=invoice.id,
                provider=provider,
                provider_payment_id=result.gateway_id,
                amount=result.amount,
                status="paid",
                raw_webhook=str(result.raw_data)[:5000],
            ))
            await _handle_payment_confirmation(invoice, db)
            await db.commit()

    return {"status": "ok"}


@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    return await _process_gateway_webhook(PaymentProvider.STRIPE, request, db)


@router.post("/webhooks/asaas")
async def asaas_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    return await _process_gateway_webhook(PaymentProvider.ASAAS, request, db)


@router.post("/webhooks/mercadopago")
async def mercadopago_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    return await _process_gateway_webhook(PaymentProvider.MERCADOPAGO, request, db)


@router.post("/webhooks/celcoin")
async def celcoin_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    return await _process_gateway_webhook(PaymentProvider.CELCOIN, request, db)
