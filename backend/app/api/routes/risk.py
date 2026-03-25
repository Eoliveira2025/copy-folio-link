"""Admin risk protection API endpoints."""

import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.exc import SQLAlchemyError
from pydantic import BaseModel

from app.core.database import get_db
from app.api.deps import require_admin
from app.models.user import User
from app.models.risk import SystemSettings, RiskIncident

logger = logging.getLogger("app.risk")
router = APIRouter()


class RiskSettingsUpdate(BaseModel):
    global_max_drawdown_percent: float | None = None
    protection_enabled: bool | None = None


class RiskSettingsResponse(BaseModel):
    global_max_drawdown_percent: float
    protection_enabled: bool
    updated_at: str


class RiskStatusResponse(BaseModel):
    total_balance: float
    total_equity: float
    current_drawdown_percent: float
    protection_enabled: bool
    max_drawdown_percent: float
    emergency_active: bool
    account_count: int


class RiskIncidentResponse(BaseModel):
    id: str
    incident_type: str
    drawdown_percent: float
    total_balance: float
    total_equity: float
    created_at: str


@router.get("/risk/settings", response_model=RiskSettingsResponse)
async def get_risk_settings(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SystemSettings).order_by(desc(SystemSettings.created_at)).limit(1)
    )
    settings = result.scalar_one_or_none()
    if not settings:
        return RiskSettingsResponse(
            global_max_drawdown_percent=50.0,
            protection_enabled=True,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
    return RiskSettingsResponse(
        global_max_drawdown_percent=settings.global_max_drawdown_percent,
        protection_enabled=settings.protection_enabled,
        updated_at=settings.updated_at.isoformat() if settings.updated_at else "",
    )


@router.put("/risk/settings", response_model=RiskSettingsResponse)
async def update_risk_settings(
    body: RiskSettingsUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SystemSettings).order_by(desc(SystemSettings.created_at)).limit(1)
    )
    settings = result.scalar_one_or_none()

    if not settings:
        settings = SystemSettings()
        db.add(settings)

    if body.global_max_drawdown_percent is not None:
        if body.global_max_drawdown_percent <= 0 or body.global_max_drawdown_percent > 100:
            raise HTTPException(status_code=400, detail="Drawdown percent must be between 0 and 100")
        settings.global_max_drawdown_percent = body.global_max_drawdown_percent

    if body.protection_enabled is not None:
        settings.protection_enabled = body.protection_enabled

    settings.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(settings)

    logger.info(
        f"Risk settings updated by admin: max_drawdown={settings.global_max_drawdown_percent}%, "
        f"enabled={settings.protection_enabled}"
    )

    return RiskSettingsResponse(
        global_max_drawdown_percent=settings.global_max_drawdown_percent,
        protection_enabled=settings.protection_enabled,
        updated_at=settings.updated_at.isoformat(),
    )


@router.get("/risk/status", response_model=RiskStatusResponse)
async def get_risk_status(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Real-time risk status with live equity data from the RiskMonitor."""
    # Get settings
    result = await db.execute(
        select(SystemSettings).order_by(desc(SystemSettings.created_at)).limit(1)
    )
    settings = result.scalar_one_or_none()
    max_dd = settings.global_max_drawdown_percent if settings else 50.0
    enabled = settings.protection_enabled if settings else True

    # Get live snapshot from RiskMonitor if running, otherwise query DB
    try:
        from app.risk_engine.global_equity_guard import GlobalEquityGuard
        emergency_active = GlobalEquityGuard.is_emergency_active()
    except Exception:
        emergency_active = False

    # Query current aggregates from DB
    from sqlalchemy import text
    agg = await db.execute(text("""
        SELECT
            COALESCE(SUM(balance), 0) AS total_balance,
            COALESCE(SUM(equity), 0) AS total_equity,
            COUNT(*) AS account_count
        FROM mt5_accounts
        WHERE status = 'connected'
    """))
    row = agg.fetchone()
    total_balance = float(row.total_balance) if row else 0.0
    total_equity = float(row.total_equity) if row else 0.0
    account_count = int(row.account_count) if row else 0

    drawdown = ((total_balance - total_equity) / total_balance * 100) if total_balance > 0 else 0.0

    return RiskStatusResponse(
        total_balance=total_balance,
        total_equity=total_equity,
        current_drawdown_percent=round(drawdown, 2),
        protection_enabled=enabled,
        max_drawdown_percent=max_dd,
        emergency_active=emergency_active,
        account_count=account_count,
    )


@router.get("/risk/incidents", response_model=list[RiskIncidentResponse])
async def list_risk_incidents(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(RiskIncident).order_by(desc(RiskIncident.created_at)).limit(50)
    )
    incidents = result.scalars().all()
    return [
        RiskIncidentResponse(
            id=str(i.id),
            incident_type=i.incident_type,
            drawdown_percent=i.drawdown_percent,
            total_balance=i.total_balance,
            total_equity=i.total_equity,
            created_at=i.created_at.isoformat(),
        )
        for i in incidents
    ]


@router.post("/risk/reset-emergency")
async def reset_emergency(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Reset emergency state and re-enable trading."""
    from app.risk_engine.global_equity_guard import GlobalEquityGuard
    import redis as redis_lib

    GlobalEquityGuard.reset_emergency()

    # Clear Redis flags
    try:
        from app.core.config import get_settings
        r = redis_lib.from_url(get_settings().REDIS_URL)
        r.delete("copytrade:trading_blocked")
        r.delete("copytrade:system_state")
    except Exception:
        pass

    # Re-enable protection in settings
    result = await db.execute(
        select(SystemSettings).order_by(desc(SystemSettings.created_at)).limit(1)
    )
    settings = result.scalar_one_or_none()
    if settings:
        settings.protection_enabled = True
        settings.updated_at = datetime.now(timezone.utc)
        await db.commit()

    logger.info("Emergency state reset by admin — trading re-enabled")
    return {"message": "Emergency state cleared, trading re-enabled"}


# ── Public Settings (no auth) ──────────────────────────

@router.get("/settings/public")
async def get_public_settings(db: AsyncSession = Depends(get_db)):
    """Public settings accessible without auth (e.g. affiliate link)."""
    try:
        result = await db.execute(
            select(SystemSettings).order_by(desc(SystemSettings.created_at)).limit(1)
        )
        settings = result.scalar_one_or_none()
    except SQLAlchemyError:
        logger.exception("Failed to load public system settings")
        settings = None

    return {
        "affiliate_broker_link": settings.affiliate_broker_link if settings else None,
    }


# ── Admin Public Settings ──────────────────────────────

class PublicSettingsUpdate(BaseModel):
    affiliate_broker_link: str | None = None


@router.put("/settings/public")
async def update_public_settings(
    body: PublicSettingsUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update public settings (affiliate link, etc.)."""
    # Validate URL if provided
    if body.affiliate_broker_link:
        import re
        url_pattern = re.compile(r'^https?://[^\s<>"{}|\\^`\[\]]+$')
        if not url_pattern.match(body.affiliate_broker_link):
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="Invalid URL format")

    result = await db.execute(
        select(SystemSettings).order_by(desc(SystemSettings.created_at)).limit(1)
    )
    settings = result.scalar_one_or_none()
    if not settings:
        settings = SystemSettings()
        db.add(settings)

    settings.affiliate_broker_link = body.affiliate_broker_link
    settings.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(settings)

    return {
        "affiliate_broker_link": settings.affiliate_broker_link,
    }
