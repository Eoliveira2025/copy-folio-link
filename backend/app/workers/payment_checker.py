"""Celery tasks for automatic payment checking and account blocking.

Scheduled tasks:
  - check_payments: runs at 08:00 and 18:00 daily
  - generate_invoices: runs daily at 00:00
  - block_overdue_accounts: runs daily at 01:00
"""

from datetime import datetime, timedelta, timezone
from celery import Celery
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.mt5_account import MT5Account, MT5Status

settings = get_settings()

celery_app = Celery("copytrade", broker=settings.REDIS_URL)

celery_app.conf.beat_schedule = {
    "check-payments-morning": {
        "task": "app.workers.payment_checker.check_payments",
        "schedule": {"hour": 8, "minute": 0},
    },
    "check-payments-evening": {
        "task": "app.workers.payment_checker.check_payments",
        "schedule": {"hour": 18, "minute": 0},
    },
    "generate-invoices-daily": {
        "task": "app.workers.payment_checker.generate_invoices",
        "schedule": {"hour": 0, "minute": 0},
    },
    "block-overdue-daily": {
        "task": "app.workers.payment_checker.block_overdue_accounts",
        "schedule": {"hour": 1, "minute": 0},
    },
}

engine = create_engine(settings.DATABASE_URL_SYNC)


@celery_app.task
def check_payments():
    """Sync pending invoices with all payment gateways."""
    with Session(engine) as db:
        pending = db.execute(
            select(Invoice).where(Invoice.status == InvoiceStatus.PENDING)
        ).scalars().all()

        for invoice in pending:
            # TODO: query each payment provider API to check payment status
            # If paid: invoice.status = InvoiceStatus.PAID, reactivate subscription
            pass

        db.commit()
    return f"Checked {len(pending)} pending invoices"


@celery_app.task
def generate_invoices():
    """Generate invoices 10 days before trial/subscription ends."""
    with Session(engine) as db:
        now = datetime.now(timezone.utc)
        threshold = now + timedelta(days=settings.INVOICE_GENERATE_BEFORE_DAYS)

        # Trials ending soon
        trials = db.execute(
            select(Subscription).where(
                Subscription.status == SubscriptionStatus.TRIAL,
                Subscription.trial_end <= threshold,
                Subscription.trial_end > now,
            )
        ).scalars().all()

        for sub in trials:
            # Check if invoice already exists
            existing = db.execute(
                select(Invoice).where(Invoice.subscription_id == sub.id)
            ).scalar_one_or_none()

            if not existing:
                due_date = sub.trial_end + timedelta(days=settings.INVOICE_DUE_AFTER_DAYS)
                db.add(Invoice(
                    subscription_id=sub.id,
                    amount=49.90,  # TODO: configurable pricing
                    currency="USD",
                    status=InvoiceStatus.PENDING,
                    due_date=due_date,
                ))

        db.commit()
    return f"Processed {len(trials)} subscriptions"


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

        for invoice in overdue_invoices:
            invoice.status = InvoiceStatus.OVERDUE

            # Block subscription
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
                # TODO: notify Copy Engine to disconnect terminal

        db.commit()
    return f"Blocked {len(overdue_invoices)} overdue accounts"
