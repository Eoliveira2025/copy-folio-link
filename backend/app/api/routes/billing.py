"""Billing endpoints: subscription status, invoices, webhook handler."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.subscription import Subscription
from app.models.invoice import Invoice, InvoiceStatus
from app.schemas.billing import SubscriptionResponse, InvoiceResponse

router = APIRouter()


@router.get("/subscription", response_model=SubscriptionResponse)
async def get_subscription(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Subscription).where(Subscription.user_id == user.id).order_by(Subscription.created_at.desc())
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="No subscription found")
    return sub


@router.get("/invoices", response_model=list[InvoiceResponse])
async def list_invoices(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Invoice)
        .join(Subscription)
        .where(Subscription.user_id == user.id)
        .order_by(Invoice.issue_date.desc())
    )
    return result.scalars().all()


@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle Stripe payment confirmation webhooks."""
    payload = await request.body()
    # TODO: verify Stripe signature with settings.STRIPE_WEBHOOK_SECRET

    import json
    event = json.loads(payload)

    if event.get("type") == "invoice.paid":
        external_id = event["data"]["object"]["id"]
        result = await db.execute(select(Invoice).where(Invoice.external_id == external_id))
        invoice = result.scalar_one_or_none()
        if invoice:
            invoice.status = InvoiceStatus.PAID
            from datetime import datetime, timezone
            invoice.paid_at = datetime.now(timezone.utc)

            # Reactivate subscription if blocked
            sub_result = await db.execute(select(Subscription).where(Subscription.id == invoice.subscription_id))
            sub = sub_result.scalar_one_or_none()
            if sub and sub.status.value == "blocked":
                sub.status = "active"
                # TODO: notify Copy Engine to reconnect MT5 account

            await db.commit()

    return {"status": "ok"}


@router.post("/webhooks/asaas")
async def asaas_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle ASAAS payment webhooks."""
    payload = await request.json()
    # TODO: implement ASAAS-specific webhook handling
    return {"status": "ok"}


@router.post("/webhooks/mercadopago")
async def mercadopago_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle Mercado Pago payment webhooks."""
    payload = await request.json()
    # TODO: implement Mercado Pago-specific webhook handling
    return {"status": "ok"}
