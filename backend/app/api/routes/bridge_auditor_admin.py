"""Admin endpoints for the Bridge Auditor (Fiscal de Execução)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.bridge_auditor_config import get_auditor_settings
from app.core.database import get_db
from app.models.user import User

router = APIRouter()


@router.get("/bridge/auditor/stats")
async def auditor_stats(_: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    cfg = get_auditor_settings()
    sql = text("""
        SELECT
          COUNT(*) FILTER (WHERE audit_status = 'pending')              AS pending,
          COUNT(*) FILTER (WHERE audit_status = 'matched')              AS matched,
          COUNT(*) FILTER (WHERE audit_status = 'not_executed')         AS not_executed,
          COUNT(*) FILTER (WHERE audit_status = 'still_open')           AS still_open,
          COUNT(*) FILTER (WHERE audit_status = 'auto_fixed')           AS auto_fixed,
          COUNT(*) FILTER (WHERE audit_status = 'auto_fix_failed')      AS auto_fix_failed,
          COUNT(*) FILTER (WHERE audit_status = 'failed_to_check')      AS failed_to_check,
          COUNT(*) FILTER (WHERE audit_status = 'sl_tp_mismatch')       AS sl_tp_mismatch,
          COUNT(*) FILTER (WHERE created_at >= now() - interval '24 hours') AS last_24h
        FROM bridge_audits
        WHERE created_at >= now() - interval '7 days'
    """)
    try:
        row = (await db.execute(sql)).fetchone()
        return {
            "enabled": cfg.BRIDGE_AUDITOR_ENABLED,
            "auto_fix_enabled": cfg.BRIDGE_AUDITOR_AUTO_FIX_ENABLED,
            "close_orphans": cfg.BRIDGE_AUDITOR_CLOSE_ORPHAN_POSITIONS,
            "pending": int(row.pending or 0),
            "matched": int(row.matched or 0),
            "not_executed": int(row.not_executed or 0),
            "still_open": int(row.still_open or 0),
            "auto_fixed": int(row.auto_fixed or 0),
            "auto_fix_failed": int(row.auto_fix_failed or 0),
            "failed_to_check": int(row.failed_to_check or 0),
            "sl_tp_mismatch": int(row.sl_tp_mismatch or 0),
            "last_24h": int(row.last_24h or 0),
        }
    except Exception:
        return {
            "enabled": cfg.BRIDGE_AUDITOR_ENABLED,
            "auto_fix_enabled": cfg.BRIDGE_AUDITOR_AUTO_FIX_ENABLED,
            "close_orphans": cfg.BRIDGE_AUDITOR_CLOSE_ORPHAN_POSITIONS,
            "pending": 0, "matched": 0, "not_executed": 0, "still_open": 0,
            "auto_fixed": 0, "auto_fix_failed": 0, "failed_to_check": 0,
            "sl_tp_mismatch": 0, "last_24h": 0,
        }


@router.get("/bridge/auditor/audits")
async def list_audits(
    status: str = Query("", description="Filter by audit_status"),
    limit: int = Query(100, ge=1, le=500),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    sql = """
        SELECT a.id, a.client_login, a.expected_action, a.expected_symbol,
               a.expected_order_type, a.expected_lot, a.master_ticket,
               a.audit_status, a.detected_status, a.failure_reason,
               a.auto_fix_attempted, a.created_at, a.checked_at,
               u.email AS user_email
        FROM bridge_audits a
        LEFT JOIN users u ON u.id = a.user_id
        WHERE 1=1
    """
    params: dict = {}
    if status:
        sql += " AND a.audit_status = :st"
        params["st"] = status
    sql += " ORDER BY a.created_at DESC LIMIT :lim"
    params["lim"] = limit
    try:
        rows = (await db.execute(text(sql), params)).fetchall()
    except Exception:
        return []
    return [
        {
            "id": str(r.id),
            "client_login": r.client_login,
            "user_email": r.user_email,
            "expected_action": r.expected_action,
            "expected_symbol": r.expected_symbol,
            "expected_order_type": r.expected_order_type,
            "expected_lot": float(r.expected_lot) if r.expected_lot is not None else None,
            "master_ticket": r.master_ticket,
            "audit_status": r.audit_status,
            "detected_status": r.detected_status,
            "failure_reason": r.failure_reason,
            "auto_fix_attempted": bool(r.auto_fix_attempted),
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "checked_at": r.checked_at.isoformat() if r.checked_at else None,
        } for r in rows
    ]
