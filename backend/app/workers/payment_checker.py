"""Celery tasks for automatic payment checking, invoice generation, and account blocking.

Scheduled tasks:
  - check_payments: runs at 08:00 and 18:00 daily
  - generate_invoices: runs daily at 00:00
  - block_overdue_accounts: runs daily at 01:00
"""

import logging
from datetime import datetime, timedelta, timezone
from celery import Celery
from celery.schedules import crontab
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.plan import Plan
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.mt5_account import MT5Account, MT5Status

settings = get_settings()
logger = logging.getLogger("workers.payment_checker")

celery_app = Celery("copytrade", broker=settings.REDIS_URL)

celery_app.conf.beat_schedule = {
    "check-payments-morning": {
        "task": "app.workers.payment_checker.check_payments",
        "schedule": crontab(hour=8, minute=0),
    },
    "check-payments-evening": {
        "task": "app.workers.payment_checker.check_payments",
        "schedule": crontab(hour=18, minute=0),
    },
    "generate-invoices-daily": {
        "task": "app.workers.payment_checker.generate_invoices",
        "schedule": crontab(hour=0, minute=0),
    },
    "block-overdue-daily": {
        "task": "app.workers.payment_checker.block_overdue_accounts",
        "schedule": crontab(hour=1, minute=0),
    },
    "access-check-every-5min": {
        "task": "app.workers.payment_checker.check_access_status",
        "schedule": 300,  # every 5 minutes
    },
}

celery_app.conf.timezone = "UTC"

engine = create_engine(settings.DATABASE_URL_SYNC)


@celery_app.task
def check_payments():
    """Sync pending invoices with all payment gateways."""
    import asyncio
    from app.services.payments import get_gateway, GatewayStatus

    with Session(engine) as db:
        pending = db.execute(
            select(Invoice).where(
                Invoice.status == InvoiceStatus.PENDING,
                Invoice.external_id.isnot(None),
                Invoice.provider.isnot(None),
            )
        ).scalars().all()

        checked = 0
        paid = 0

        loop = asyncio.new_event_loop()

        for invoice in pending:
            try:
                gateway = get_gateway(invoice.provider.value)
                result = loop.run_until_complete(
                    gateway.check_status(invoice.external_id)
                )
                checked += 1

                if result.status == GatewayStatus.PAID:
                    invoice.status = InvoiceStatus.PAID
                    invoice.paid_at = datetime.now(timezone.utc)
                    paid += 1

                    # Reactivate subscription and advance billing date
                    sub = db.execute(
                        select(Subscription).where(Subscription.id == invoice.subscription_id)
                    ).scalar_one_or_none()
                    if sub:
                        if sub.status == SubscriptionStatus.BLOCKED:
                            sub.status = SubscriptionStatus.ACTIVE

                        # Advance next_billing_date after successful payment
                        now = datetime.now(timezone.utc)
                        cycle = sub.billing_cycle_days or 30
                        sub.current_period_start = now
                        sub.current_period_end = now + timedelta(days=cycle)
                        sub.next_billing_date = now + timedelta(days=cycle)

                        # Reconnect MT5 accounts
                        accounts = db.execute(
                            select(MT5Account).where(
                                MT5Account.user_id == sub.user_id,
                                MT5Account.status == MT5Status.BLOCKED,
                            )
                        ).scalars().all()
                        for account in accounts:
                            account.status = MT5Status.CONNECTED
                            try:
                                import redis as redis_lib
                                import json
                                r = redis_lib.from_url(settings.REDIS_URL)
                                r.publish("copytrade:terminal:commands", json.dumps({
                                    "action": "spawn",
                                    "account_id": str(account.id),
                                    "login": account.login,
                                    "encrypted_password": account.encrypted_password,
                                    "server": account.server,
                                }))
                            except Exception:
                                pass
            except Exception as e:
                logger.error(f"Error checking invoice {invoice.id}: {e}")

        loop.close()
        db.commit()
    return f"Checked {checked} invoices, {paid} newly paid"


@celery_app.task
def generate_invoices():
    """Generate invoices based on next_billing_date for recurring billing.

    Handles two scenarios:
    1. Trial subscriptions approaching trial_end → generate first invoice, set next_billing_date
    2. Active subscriptions where next_billing_date has arrived → generate recurring invoice
    """
    with Session(engine) as db:
        now = datetime.now(timezone.utc)
        lookahead = now + timedelta(days=settings.INVOICE_GENERATE_BEFORE_DAYS)
        created = 0

        # ── Scenario 1: Trial ending soon — first invoice ──────────
        trials = db.execute(
            select(Subscription).where(
                Subscription.status == SubscriptionStatus.TRIAL,
                Subscription.trial_end <= lookahead,
                Subscription.trial_end > now,
                Subscription.next_billing_date.is_(None),  # No billing date set yet
            )
        ).scalars().all()

        for sub in trials:
            # Check no pending/unpaid invoice exists for this subscription
            existing_pending = db.execute(
                select(Invoice).where(
                    Invoice.subscription_id == sub.id,
                    Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.OVERDUE]),
                )
            ).scalar_one_or_none()

            if not existing_pending:
                price = settings.SUBSCRIPTION_PRICE
                currency = settings.SUBSCRIPTION_CURRENCY
                if sub.plan_id:
                    plan = db.execute(select(Plan).where(Plan.id == sub.plan_id)).scalar_one_or_none()
                    if plan:
                        price = plan.price

                due_date = sub.trial_end + timedelta(days=settings.INVOICE_DUE_AFTER_DAYS)
                db.add(Invoice(
                    subscription_id=sub.id,
                    amount=price,
                    currency=currency,
                    status=InvoiceStatus.PENDING,
                    issue_date=now,
                    due_date=due_date,
                ))

                # Initialize billing schedule
                cycle = sub.billing_cycle_days or 30
                sub.next_billing_date = sub.trial_end + timedelta(days=cycle)
                created += 1

        # ── Scenario 2: Recurring billing — next_billing_date reached ──
        recurring = db.execute(
            select(Subscription).where(
                Subscription.status == SubscriptionStatus.ACTIVE,
                Subscription.next_billing_date.isnot(None),
                Subscription.next_billing_date <= lookahead,
            )
        ).scalars().all()

        for sub in recurring:
            # Only generate if no pending/overdue invoice exists
            existing_pending = db.execute(
                select(Invoice).where(
                    Invoice.subscription_id == sub.id,
                    Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.OVERDUE]),
                )
            ).scalar_one_or_none()

            if not existing_pending:
                price = settings.SUBSCRIPTION_PRICE
                currency = settings.SUBSCRIPTION_CURRENCY
                if sub.plan_id:
                    plan = db.execute(select(Plan).where(Plan.id == sub.plan_id)).scalar_one_or_none()
                    if plan:
                        price = plan.price

                due_date = sub.next_billing_date + timedelta(days=settings.INVOICE_DUE_AFTER_DAYS)
                db.add(Invoice(
                    subscription_id=sub.id,
                    amount=price,
                    currency=currency,
                    status=InvoiceStatus.PENDING,
                    issue_date=now,
                    due_date=due_date,
                ))

                # Advance next_billing_date to prevent duplicate generation
                cycle = sub.billing_cycle_days or 30
                sub.next_billing_date = sub.next_billing_date + timedelta(days=cycle)
                created += 1

        db.commit()
    return f"Created {created} invoices (trials: {len(trials)}, recurring: {len(recurring)})"


@celery_app.task
def block_overdue_accounts():
    """Block accounts with invoices overdue by more than BLOCK_AFTER_OVERDUE_DAYS."""
    with Session(engine) as db:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=settings.BLOCK_AFTER_OVERDUE_DAYS)

        overdue_invoices = db.execute(
            select(Invoice).where(
                Invoice.status == InvoiceStatus.PENDING,
                Invoice.due_date <= cutoff,
            )
        ).scalars().all()

        blocked = 0
        for invoice in overdue_invoices:
            invoice.status = InvoiceStatus.OVERDUE

            sub = db.execute(
                select(Subscription).where(Subscription.id == invoice.subscription_id)
            ).scalar_one()
            sub.status = SubscriptionStatus.BLOCKED

            # Disconnect MT5 accounts
            mt5_accounts = db.execute(
                select(MT5Account).where(MT5Account.user_id == sub.user_id)
            ).scalars().all()
            for account in mt5_accounts:
                account.status = MT5Status.BLOCKED
                try:
                    import redis as redis_lib
                    import json
                    r = redis_lib.from_url(settings.REDIS_URL)
                    r.publish("copytrade:terminal:commands", json.dumps({
                        "action": "stop",
                        "account_id": str(account.id),
                        "login": account.login,
                    }))
                except Exception:
                    pass

            blocked += 1

        db.commit()
    return f"Blocked {blocked} overdue accounts"
