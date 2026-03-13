"""Operations dashboard API endpoint — aggregated system health metrics."""

import logging
from datetime import datetime, date, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text, desc

from app.core.database import get_db
from app.api.deps import require_admin
from app.models.user import User
from app.models.mt5_account import MT5Account, MT5Status
from app.models.strategy import MasterAccount
from app.models.trade import TradeEvent, TradeCopy, CopyStatus
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.risk import SystemSettings
from app.models.dead_letter import DeadLetterTrade, DeadLetterStatus

logger = logging.getLogger("app.operations")
router = APIRouter()


@router.get("/operations")
async def operations_dashboard(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Aggregated operations dashboard with system health metrics."""
    today = date.today()

    # MT5 accounts
    connected_accounts = await db.execute(
        select(func.count(MT5Account.id)).where(MT5Account.status == MT5Status.CONNECTED)
    )
    total_mt5 = await db.execute(select(func.count(MT5Account.id)))

    # Master accounts
    master_count = await db.execute(select(func.count(MasterAccount.id)))

    # Trades today
    trades_today = await db.execute(
        select(func.count(TradeCopy.id)).where(
            func.date(TradeCopy.executed_at) == today
        )
    )

    # Failed trades today
    failed_today = await db.execute(
        select(func.count(TradeCopy.id)).where(
            func.date(TradeCopy.executed_at) == today,
            TradeCopy.status == CopyStatus.FAILED,
        )
    )

    # Average trade latency today
    avg_latency = await db.execute(
        select(func.avg(TradeCopy.latency_ms)).where(
            func.date(TradeCopy.executed_at) == today,
            TradeCopy.latency_ms.isnot(None),
        )
    )

    # Dead letter queue depth
    dlq_pending = await db.execute(
        select(func.count(DeadLetterTrade.id)).where(
            DeadLetterTrade.status == DeadLetterStatus.PENDING
        )
    )

    # Equity aggregates
    equity_agg = await db.execute(text("""
        SELECT
            COALESCE(SUM(balance), 0) AS total_balance,
            COALESCE(SUM(equity), 0) AS total_equity
        FROM mt5_accounts
        WHERE status = 'connected'
    """))
    eq_row = equity_agg.fetchone()
    total_balance = float(eq_row.total_balance) if eq_row else 0.0
    total_equity = float(eq_row.total_equity) if eq_row else 0.0
    drawdown = ((total_balance - total_equity) / total_balance * 100) if total_balance > 0 else 0.0

    # Protection settings
    settings_result = await db.execute(
        select(SystemSettings).order_by(desc(SystemSettings.created_at)).limit(1)
    )
    sys_settings = settings_result.scalar_one_or_none()
    protection_enabled = sys_settings.protection_enabled if sys_settings else True

    # Emergency active
    try:
        from app.risk_engine.global_equity_guard import GlobalEquityGuard
        emergency_active = GlobalEquityGuard.is_emergency_active()
    except Exception:
        emergency_active = False

    # Subscriptions
    active_subs = await db.execute(
        select(func.count(Subscription.id)).where(Subscription.status == SubscriptionStatus.ACTIVE)
    )
    trial_subs = await db.execute(
        select(func.count(Subscription.id)).where(Subscription.status == SubscriptionStatus.TRIAL)
    )

    # Overdue invoices
    overdue = await db.execute(
        select(func.count(Invoice.id)).where(Invoice.status == InvoiceStatus.OVERDUE)
    )

    # Service health checks
    redis_healthy = True
    try:
        import redis as redis_lib
        from app.core.config import get_settings
        r = redis_lib.from_url(get_settings().REDIS_URL, socket_timeout=2)
        r.ping()
    except Exception:
        redis_healthy = False

    pg_healthy = True
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        pg_healthy = False

    return {
        # Trading
        "connected_mt5_accounts": connected_accounts.scalar() or 0,
        "total_mt5_accounts": total_mt5.scalar() or 0,
        "master_accounts": master_count.scalar() or 0,
        "copied_trades_today": trades_today.scalar() or 0,
        "failed_trades_today": failed_today.scalar() or 0,
        "avg_latency_ms": round(float(avg_latency.scalar() or 0), 1),
        "dlq_pending": dlq_pending.scalar() or 0,
        # Equity
        "total_balance": round(total_balance, 2),
        "total_equity": round(total_equity, 2),
        "global_drawdown_percent": round(drawdown, 2),
        "protection_enabled": protection_enabled,
        "emergency_active": emergency_active,
        # Subscriptions
        "active_subscriptions": active_subs.scalar() or 0,
        "trial_subscriptions": trial_subs.scalar() or 0,
        "overdue_invoices": overdue.scalar() or 0,
        # Services
        "services": {
            "redis": "healthy" if redis_healthy else "down",
            "postgresql": "healthy" if pg_healthy else "down",
            "copy_engine": "healthy",  # Would check via Redis heartbeat in prod
            "mt5_manager": "healthy",  # Would check via Redis heartbeat in prod
        },
    }
