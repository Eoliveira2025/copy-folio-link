"""Access status checker — runs periodically to enforce billing-based access control.

Rules:
  - 3 days before due_date  → WARNING
  - Due day                 → WARNING (strong)
  - Up to 2 days overdue    → GRACE (still can operate)
  - 3+ days overdue         → BLOCKED (disconnect MT5, prevent reconnection)

Scheduled via Celery beat every 5 minutes.
"""

import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine, select, and_
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.subscription import Subscription, SubscriptionStatus, AccessStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.mt5_account import MT5Account, MT5Status

settings = get_settings()
logger = logging.getLogger("workers.access_checker")
audit_logger = logging.getLogger("app.audit.access_control")

engine = create_engine(settings.DATABASE_URL_SYNC)


def run_access_check():
    """Main access check logic. Called by Celery task or standalone."""
    with Session(engine) as db:
        now = datetime.now(timezone.utc)
        checked = 0
        warnings = 0
        graced = 0
        blocked = 0

        # Get all active/trial subscriptions that are NOT manually overridden
        subs = db.execute(
            select(Subscription).where(
                Subscription.status.in_([
                    SubscriptionStatus.ACTIVE,
                    SubscriptionStatus.TRIAL,
                ]),
                Subscription.manual_override == False,
            )
        ).scalars().all()

        for sub in subs:
            checked += 1

            # Find the most recent unpaid invoice (pending or overdue)
            invoice = db.execute(
                select(Invoice).where(
                    Invoice.subscription_id == sub.id,
                    Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.OVERDUE]),
                ).order_by(Invoice.due_date.desc())
            ).scalars().first()

            old_status = sub.access_status
            new_status = AccessStatus.ACTIVE

            if invoice:
                days_until_due = (invoice.due_date.replace(tzinfo=timezone.utc) - now).days
                days_overdue = -days_until_due  # positive when overdue

                if days_until_due <= 3 and days_until_due > 0:
                    # 3 days before due → warning
                    new_status = AccessStatus.WARNING
                elif days_until_due == 0:
                    # Due today → warning
                    new_status = AccessStatus.WARNING
                elif days_overdue > 0 and days_overdue <= 2:
                    # 1-2 days overdue → grace
                    new_status = AccessStatus.GRACE
                elif days_overdue >= 3:
                    # 3+ days overdue → blocked
                    new_status = AccessStatus.BLOCKED

            # Also check trial expiration
            if sub.status == SubscriptionStatus.TRIAL and sub.trial_end:
                trial_end = sub.trial_end.replace(tzinfo=timezone.utc) if sub.trial_end.tzinfo is None else sub.trial_end
                days_until_trial_end = (trial_end - now).days

                if days_until_trial_end <= 3 and days_until_trial_end > 0:
                    if new_status == AccessStatus.ACTIVE:
                        new_status = AccessStatus.WARNING
                elif days_until_trial_end <= 0:
                    # Trial expired and no paid invoice
                    if not invoice or invoice.status != InvoiceStatus.PAID:
                        days_past_trial = -days_until_trial_end
                        if days_past_trial <= 2:
                            new_status = AccessStatus.GRACE
                        else:
                            new_status = AccessStatus.BLOCKED

            sub.last_access_check = now

            if new_status != old_status:
                sub.access_status = new_status
                audit_logger.info(
                    f"Access status changed: user={sub.user_id} "
                    f"{old_status.value if old_status else 'none'} → {new_status.value}"
                )

                if new_status == AccessStatus.WARNING:
                    warnings += 1
                elif new_status == AccessStatus.GRACE:
                    graced += 1
                elif new_status == AccessStatus.BLOCKED:
                    blocked += 1
                    sub.blocked_at = now
                    sub.status = SubscriptionStatus.BLOCKED
                    _disconnect_user_mt5(db, sub)

                # If transitioning back to active, clear blocked_at
                if new_status == AccessStatus.ACTIVE and old_status in (AccessStatus.BLOCKED, AccessStatus.GRACE, AccessStatus.WARNING):
                    sub.blocked_at = None

        db.commit()

    result = f"Access check: {checked} subs, {warnings} warnings, {graced} grace, {blocked} blocked"
    logger.info(result)
    return result


def _disconnect_user_mt5(db: Session, sub: Subscription):
    """Disconnect all MT5 accounts for a user. Idempotent — skips already blocked."""
    accounts = db.execute(
        select(MT5Account).where(
            MT5Account.user_id == sub.user_id,
            MT5Account.status != MT5Status.BLOCKED,
            MT5Account.status != MT5Status.DISCONNECTED,
        )
    ).scalars().all()

    for account in accounts:
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
            r.lpush("copytrade:terminal:queue", json.dumps({
                "action": "stop",
                "account_id": str(account.id),
                "login": account.login,
            }))
        except Exception as e:
            logger.error(f"Failed to dispatch disconnect for {account.login}: {e}")

        audit_logger.warning(
            f"AUDIT: MT5 account {account.login} BLOCKED due to overdue invoice (user={sub.user_id})"
        )
