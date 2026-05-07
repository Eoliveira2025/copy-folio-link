"""Admin endpoints to inspect Bridge state (read-only)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.bridge_config import get_bridge_settings
from app.core.database import get_db
from app.models.user import User

router = APIRouter()


@router.get("/bridge/stats")
async def bridge_stats(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    cfg = get_bridge_settings()
    sql = text("""
        SELECT
          (SELECT COUNT(*) FROM bridge_signals WHERE created_at >= now() - interval '24 hours') AS signals_24h,
          (SELECT COUNT(*) FROM bridge_execution_orders WHERE status = 'queued') AS orders_queued,
          (SELECT COUNT(*) FROM bridge_execution_orders WHERE status = 'executed') AS orders_executed,
          (SELECT COUNT(*) FROM bridge_execution_orders WHERE status IN ('failed','enqueue_failed','skipped_lot_too_small')) AS orders_failed
    """)
    try:
        row = (await db.execute(sql)).fetchone()
        return {
            "enabled": cfg.BRIDGE_ENABLED,
            "signals_24h": int(row.signals_24h or 0),
            "orders_queued": int(row.orders_queued or 0),
            "orders_executed": int(row.orders_executed or 0),
            "orders_failed": int(row.orders_failed or 0),
        }
    except Exception:
        return {"enabled": cfg.BRIDGE_ENABLED, "signals_24h": 0,
                "orders_queued": 0, "orders_executed": 0, "orders_failed": 0}


@router.get("/bridge/signals")
async def bridge_signals(
    limit: int = Query(50, ge=1, le=500),
    master_id: str = Query("", description="Filter by master_id"),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    sql = "SELECT id, master_id, strategy_id, action, symbol, volume, status, created_at, processed_at FROM bridge_signals WHERE 1=1"
    params: dict = {}
    if master_id:
        sql += " AND master_id = :mid"
        params["mid"] = master_id
    sql += " ORDER BY created_at DESC LIMIT :lim"
    params["lim"] = limit
    try:
        rows = (await db.execute(text(sql), params)).fetchall()
    except Exception:
        return []
    return [
        {
            "id": str(r.id),
            "master_id": r.master_id,
            "strategy_id": r.strategy_id,
            "action": r.action,
            "symbol": r.symbol,
            "volume": float(r.volume),
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "processed_at": r.processed_at.isoformat() if r.processed_at else None,
        } for r in rows
    ]
