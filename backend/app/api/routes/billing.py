"""Billing endpoints: checkout, invoices, webhooks, and admin management."""

import logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

logger = logging.getLogger("app.billing")

from app.core.database import get_db
from app.core.config import get_settings
from app.api.deps import get_current_user, require_admin
from app.models.user import User
from app.models.plan import Plan
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.invoice import Invoice, InvoiceStatus, Payment, PaymentProvider
from app.models.mt5_account import MT5Account, MT5Status
from app.models.upgrade_request import UpgradeRequest, UpgradeRequestStatus
from app.schemas.billing import (
    SubscriptionResponse, InvoiceResponse, CheckoutRequest, CheckoutResponse,
    UpgradeRequestCreate, UpgradeRequestResponse,
    AdminSubscriptionResponse, AdminInvoiceResponse,
    AdminCancelSubscriptionRequest, AdminRefundRequest, BillingStatsResponse,
)
from app.services.payments import get_gateway, GatewayStatus, BillingType
from app.services import copy_engine

settings = get_settings()
router = APIRouter()


# ── Public ────────────────────────────────────────────────

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


# ── User: Subscription & Invoices ──────────────────────────

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

    return SubscriptionResponse(
        id=sub.id,
        status=sub.status.value,
        plan_name=sub.plan.name if sub.plan else None,
        plan_price=sub.plan.price if sub.plan else None,
        plan_currency=sub.plan.currency if sub.plan else None,
        trial_start=sub.trial_start,
        trial_end=sub.trial_end,
        current_period_start=sub.current_period_start,
        current_period_end=sub.current_period_end,
        next_billing_date=sub.next_billing_date,
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


# ── Checkout ───────────────────────────────────────────────

@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    body: CheckoutRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a payment charge via the selected gateway and return checkout URL."""

    # Validate plan
    plan_result = await db.execute(select(Plan).where(Plan.id == body.plan_id, Plan.active == True))
    plan = plan_result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found or inactive")

    # Get or create subscription
    sub_result = await db.execute(
        select(Subscription).where(Subscription.user_id == user.id).order_by(Subscription.created_at.desc())
    )
    sub = sub_result.scalar_one_or_none()
    if not sub:
        now = datetime.now(timezone.utc)
        sub = Subscription(
            user_id=user.id,
            plan_id=plan.id,
            status=SubscriptionStatus.TRIAL,
            trial_start=now,
            trial_end=now + timedelta(days=plan.trial_days or 30),
        )
        db.add(sub)
        await db.flush()
    else:
        # Update plan on subscription if upgrading
        sub.plan_id = plan.id

    # Check no pending invoice for this subscription
    existing = await db.execute(
        select(Invoice).where(
            Invoice.subscription_id == sub.id,
            Invoice.status == InvoiceStatus.PENDING,
        )
    )
    existing_invoice = existing.scalar_one_or_none()

    if existing_invoice and existing_invoice.external_id:
        # Return existing checkout info
        return CheckoutResponse(
            invoice_id=existing_invoice.id,
            gateway_id=existing_invoice.external_id,
            checkout_url=None,  # User should use the original URL
            status="pending",
        )

    # Map billing type
    billing_type_map = {
        "PIX": BillingType.PIX,
        "BOLETO": BillingType.BOLETO,
        "CREDIT_CARD": BillingType.CREDIT_CARD,
        "UNDEFINED": BillingType.UNDEFINED,
    }
    billing_type = billing_type_map.get(body.billing_type.upper(), BillingType.UNDEFINED)

    # Map provider
    provider_map = {
        "asaas": PaymentProvider.ASAAS,
        "stripe": PaymentProvider.STRIPE,
        "mercadopago": PaymentProvider.MERCADOPAGO,
        "celcoin": PaymentProvider.CELCOIN,
    }
    provider = provider_map.get(body.gateway.lower())
    if not provider:
        raise HTTPException(status_code=400, detail=f"Unknown gateway: {body.gateway}")

    # Create charge via gateway
    try:
        gateway = get_gateway(body.gateway)
        result = await gateway.create_charge(
            amount=plan.price,
            currency=plan.currency,
            description=f"CopyTrade Pro - Plano {plan.name}",
            customer_email=user.email,
            customer_name=user.full_name,
            billing_type=billing_type,
        )
    except Exception as e:
        logger.error(f"Gateway error creating charge: {e}")
        raise HTTPException(status_code=502, detail="Payment gateway error")

    # Create invoice
    due_date = datetime.now(timezone.utc) + timedelta(days=settings.INVOICE_DUE_AFTER_DAYS)
    invoice = Invoice(
        subscription_id=sub.id,
        amount=plan.price,
        currency=plan.currency,
        status=InvoiceStatus.PENDING,
        issue_date=datetime.now(timezone.utc),
        due_date=due_date,
        external_id=result.gateway_id,
        provider=provider,
    )
    db.add(invoice)
    await db.commit()
    await db.refresh(invoice)

    return CheckoutResponse(
        invoice_id=invoice.id,
        gateway_id=result.gateway_id,
        checkout_url=result.checkout_url,
        pix_qr_code=result.pix_qr_code,
        pix_copy_paste=result.pix_copy_paste,
        boleto_url=result.boleto_url,
        status="pending",
    )


@router.get("/checkout/{invoice_id}/status")
async def check_checkout_status(
    invoice_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Poll payment status for a specific invoice."""
    import uuid as uuid_mod
    try:
        inv_uuid = uuid_mod.UUID(invoice_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid invoice ID")

    inv_result = await db.execute(
        select(Invoice)
        .join(Subscription)
        .where(Invoice.id == inv_uuid, Subscription.user_id == user.id)
    )
    invoice = inv_result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    # If already paid, just return
    if invoice.status == InvoiceStatus.PAID:
        return {"status": "paid", "paid_at": invoice.paid_at}

    # Check with gateway
    if invoice.external_id and invoice.provider:
        try:
            gateway = get_gateway(invoice.provider.value)
            result = await gateway.check_status(invoice.external_id)
            if result.status == GatewayStatus.PAID:
                await _handle_payment_confirmation(invoice, db)
                await db.commit()
                return {"status": "paid", "paid_at": invoice.paid_at}
        except Exception as e:
            logger.warning(f"Error checking payment status: {e}")

    return {"status": invoice.status.value}


# ── Upgrade Requests ────────────────────────────────────

@router.get("/upgrade-check")
async def check_upgrade_eligibility(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
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

    mt5_result = await db.execute(select(MT5Account).where(MT5Account.user_id == user.id))
    mt5 = mt5_result.scalars().first()
    balance = mt5.balance if mt5 and mt5.balance else 0.0

    next_plan_result = await db.execute(
        select(Plan).where(
            Plan.active == True,
            Plan.price > (current_plan.price if current_plan else 0)
        ).order_by(Plan.price).limit(1)
    )
    next_plan = next_plan_result.scalar_one_or_none()
    if not next_plan:
        return {"eligible": False, "reason": "Already on highest plan"}

    pending = await db.execute(
        select(UpgradeRequest).where(
            UpgradeRequest.user_id == user.id,
            UpgradeRequest.status == UpgradeRequestStatus.PENDING,
        )
    )
    has_pending = pending.scalar_one_or_none() is not None

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
    pending = await db.execute(
        select(UpgradeRequest).where(
            UpgradeRequest.user_id == user.id,
            UpgradeRequest.status == UpgradeRequestStatus.PENDING,
        )
    )
    if pending.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="You already have a pending upgrade request")

    target_result = await db.execute(select(Plan).where(Plan.id == body.target_plan_id, Plan.active == True))
    target_plan = target_result.scalar_one_or_none()
    if not target_plan:
        raise HTTPException(status_code=404, detail="Target plan not found or inactive")

    sub_result = await db.execute(
        select(Subscription).where(Subscription.user_id == user.id).order_by(Subscription.created_at.desc())
    )
    sub = sub_result.scalar_one_or_none()
    current_plan_id = sub.plan_id if sub else None

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


# ── Payment confirmation logic ─────────────────────────────

async def _handle_payment_confirmation(invoice: Invoice, db: AsyncSession):
    """Mark invoice paid, advance billing, reactivate subscription."""
    invoice.status = InvoiceStatus.PAID
    invoice.paid_at = datetime.now(timezone.utc)

    sub = await db.execute(select(Subscription).where(Subscription.id == invoice.subscription_id))
    subscription = sub.scalar_one_or_none()
    if subscription:
        now = datetime.now(timezone.utc)
        cycle = subscription.billing_cycle_days or 30

        subscription.current_period_start = now
        subscription.current_period_end = now + timedelta(days=cycle)
        subscription.next_billing_date = now + timedelta(days=cycle)

        if subscription.status in (SubscriptionStatus.BLOCKED, SubscriptionStatus.TRIAL):
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


# ── Webhooks ───────────────────────────────────────────────

async def _process_gateway_webhook(provider: PaymentProvider, request: Request, db: AsyncSession):
    """Generic webhook handler for all gateways."""
    payload = await request.json()

    # Optional: verify webhook token for Asaas
    if provider == PaymentProvider.ASAAS:
        token = request.headers.get("asaas-access-token", "")
        expected = settings.ASAAS_WEBHOOK_TOKEN
        if expected and token != expected:
            logger.warning("Invalid Asaas webhook token")
            raise HTTPException(status_code=401, detail="Invalid webhook token")

    gateway = get_gateway(provider.value)
    result = await gateway.process_webhook(payload)

    if result.status == GatewayStatus.PAID and result.gateway_id:
        inv = await db.execute(select(Invoice).where(Invoice.external_id == result.gateway_id))
        invoice = inv.scalar_one_or_none()
        if invoice:
            if invoice.status == InvoiceStatus.PAID:
                logger.info(f"Duplicate webhook ignored for invoice {invoice.id}")
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

    elif result.status == GatewayStatus.REFUNDED and result.gateway_id:
        inv = await db.execute(select(Invoice).where(Invoice.external_id == result.gateway_id))
        invoice = inv.scalar_one_or_none()
        if invoice and invoice.status != InvoiceStatus.CANCELLED:
            invoice.status = InvoiceStatus.CANCELLED
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


# ══════════════════════════════════════════════════════════
# ADMIN ENDPOINTS
# ══════════════════════════════════════════════════════════

@router.get("/admin/stats", response_model=BillingStatsResponse)
async def admin_billing_stats(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Dashboard stats for admin billing overview."""
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Subscription counts
    active_count = (await db.execute(
        select(func.count()).select_from(Subscription).where(Subscription.status == SubscriptionStatus.ACTIVE)
    )).scalar() or 0

    trial_count = (await db.execute(
        select(func.count()).select_from(Subscription).where(Subscription.status == SubscriptionStatus.TRIAL)
    )).scalar() or 0

    blocked_count = (await db.execute(
        select(func.count()).select_from(Subscription).where(Subscription.status == SubscriptionStatus.BLOCKED)
    )).scalar() or 0

    # Invoice counts
    pending_count = (await db.execute(
        select(func.count()).select_from(Invoice).where(Invoice.status == InvoiceStatus.PENDING)
    )).scalar() or 0

    overdue_count = (await db.execute(
        select(func.count()).select_from(Invoice).where(Invoice.status == InvoiceStatus.OVERDUE)
    )).scalar() or 0

    # Paid this month
    paid_month = (await db.execute(
        select(func.count()).select_from(Invoice).where(
            Invoice.status == InvoiceStatus.PAID,
            Invoice.paid_at >= month_start,
        )
    )).scalar() or 0

    # Total revenue (all time)
    total_revenue = (await db.execute(
        select(func.coalesce(func.sum(Invoice.amount), 0)).where(Invoice.status == InvoiceStatus.PAID)
    )).scalar() or 0

    return BillingStatsResponse(
        total_revenue=float(total_revenue),
        active_subscriptions=active_count,
        trial_subscriptions=trial_count,
        blocked_subscriptions=blocked_count,
        pending_invoices=pending_count,
        overdue_invoices=overdue_count,
        paid_invoices_this_month=paid_month,
    )


@router.get("/admin/subscriptions")
async def admin_list_subscriptions(
    status: str | None = None,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """List all subscriptions with user and plan info."""
    query = (
        select(Subscription)
        .options(selectinload(Subscription.plan), selectinload(Subscription.user))
        .order_by(Subscription.created_at.desc())
    )
    if status:
        try:
            sub_status = SubscriptionStatus(status)
            query = query.where(Subscription.status == sub_status)
        except ValueError:
            pass

    result = await db.execute(query)
    subs = result.scalars().all()

    return [
        AdminSubscriptionResponse(
            id=s.id,
            user_id=s.user_id,
            user_email=s.user.email if s.user else None,
            plan_name=s.plan.name if s.plan else None,
            plan_price=s.plan.price if s.plan else None,
            status=s.status.value,
            trial_start=s.trial_start,
            trial_end=s.trial_end,
            current_period_start=s.current_period_start,
            current_period_end=s.current_period_end,
            next_billing_date=s.next_billing_date,
            auto_renew=s.auto_renew,
            created_at=s.created_at,
        )
        for s in subs
    ]


@router.get("/admin/invoices")
async def admin_list_invoices(
    status: str | None = None,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """List all invoices with user info."""
    query = (
        select(Invoice)
        .join(Subscription)
        .options(selectinload(Invoice.subscription).selectinload(Subscription.user))
        .options(selectinload(Invoice.subscription).selectinload(Subscription.plan))
        .order_by(Invoice.issue_date.desc())
    )
    if status:
        try:
            inv_status = InvoiceStatus(status)
            query = query.where(Invoice.status == inv_status)
        except ValueError:
            pass

    result = await db.execute(query)
    invoices = result.scalars().all()

    return [
        AdminInvoiceResponse(
            id=inv.id,
            subscription_id=inv.subscription_id,
            user_email=inv.subscription.user.email if inv.subscription and inv.subscription.user else None,
            plan_name=inv.subscription.plan.name if inv.subscription and inv.subscription.plan else None,
            amount=inv.amount,
            currency=inv.currency,
            status=inv.status.value,
            issue_date=inv.issue_date,
            due_date=inv.due_date,
            paid_at=inv.paid_at,
            provider=inv.provider.value if inv.provider else None,
            external_id=inv.external_id,
        )
        for inv in invoices
    ]


@router.post("/admin/subscriptions/{subscription_id}/cancel")
async def admin_cancel_subscription(
    subscription_id: str,
    body: AdminCancelSubscriptionRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin cancels a subscription and blocks MT5 accounts."""
    import uuid as uuid_mod
    try:
        sub_uuid = uuid_mod.UUID(subscription_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid subscription ID")

    sub_result = await db.execute(select(Subscription).where(Subscription.id == sub_uuid))
    sub = sub_result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    sub.status = SubscriptionStatus.BLOCKED
    sub.auto_renew = False

    # Cancel pending invoices
    pending_invoices = await db.execute(
        select(Invoice).where(
            Invoice.subscription_id == sub.id,
            Invoice.status == InvoiceStatus.PENDING,
        )
    )
    for inv in pending_invoices.scalars().all():
        inv.status = InvoiceStatus.CANCELLED

    # Block MT5 accounts
    mt5_accounts = await db.execute(select(MT5Account).where(MT5Account.user_id == sub.user_id))
    for account in mt5_accounts.scalars().all():
        account.status = MT5Status.BLOCKED
        try:
            copy_engine.dispatch_block_account(str(account.id), account.login)
        except Exception:
            pass

    await db.commit()
    return {"message": "Subscription cancelled", "reason": body.reason}


@router.post("/admin/refund")
async def admin_refund_invoice(
    body: AdminRefundRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin refunds a paid invoice via the original gateway."""
    inv_result = await db.execute(select(Invoice).where(Invoice.id == body.invoice_id))
    invoice = inv_result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if invoice.status != InvoiceStatus.PAID:
        raise HTTPException(status_code=400, detail="Only paid invoices can be refunded")

    if not invoice.external_id or not invoice.provider:
        raise HTTPException(status_code=400, detail="Invoice has no gateway reference for refund")

    try:
        gateway = get_gateway(invoice.provider.value)
        result = await gateway.refund(invoice.external_id, body.amount)
    except NotImplementedError:
        raise HTTPException(status_code=400, detail=f"Refund not supported for {invoice.provider.value}")
    except Exception as e:
        logger.error(f"Refund error: {e}")
        raise HTTPException(status_code=502, detail="Gateway refund error")

    invoice.status = InvoiceStatus.CANCELLED

    db.add(Payment(
        invoice_id=invoice.id,
        provider=invoice.provider,
        provider_payment_id=result.gateway_id,
        amount=body.amount or invoice.amount,
        status="refunded",
        raw_webhook=str(result.raw_data)[:5000],
    ))

    await db.commit()
    return {"message": "Refund processed", "gateway_id": result.gateway_id}
