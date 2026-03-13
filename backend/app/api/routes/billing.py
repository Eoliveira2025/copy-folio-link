"""Billing endpoints with plan-aware subscription and full payment gateway integration."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.plan import Plan
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.invoice import Invoice, InvoiceStatus, Payment, PaymentProvider
from app.schemas.billing import SubscriptionResponse, InvoiceResponse
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
            "allowed_strategies": p.allowed_strategies,
            "trial_days": p.trial_days,
            "max_accounts": p.max_accounts,
        }
        for p in plans
    ]


@router.get("/subscription")
async def get_subscription(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Subscription).where(Subscription.user_id == user.id).order_by(Subscription.created_at.desc())
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="No subscription found")

    plan_name = None
    plan_price = None
    if sub.plan_id:
        plan_result = await db.execute(select(Plan).where(Plan.id == sub.plan_id))
        plan = plan_result.scalar_one_or_none()
        if plan:
            plan_name = plan.name
            plan_price = plan.price

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


async def _handle_payment_confirmation(invoice: Invoice, db: AsyncSession):
    """Shared logic for marking invoice paid and reactivating subscription."""
    invoice.status = InvoiceStatus.PAID
    invoice.paid_at = datetime.now(timezone.utc)

    sub = await db.execute(select(Subscription).where(Subscription.id == invoice.subscription_id))
    subscription = sub.scalar_one_or_none()
    if subscription and subscription.status == SubscriptionStatus.BLOCKED:
        subscription.status = SubscriptionStatus.ACTIVE

        from app.models.mt5_account import MT5Account, MT5Status
        from app.models.strategy import Strategy, MasterAccount, UserStrategy

        mt5_result = await db.execute(
            select(MT5Account).where(MT5Account.user_id == subscription.user_id)
        )
        for account in mt5_result.scalars().all():
            account.status = MT5Status.CONNECTED

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
