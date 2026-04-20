"""Admin endpoint: list trade copy recoveries (failure & retry audit)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_, func, text

from app.core.database import get_db
from app.api.deps import require_admin
from app.models.user import User
from app.models.copy_recovery import TradeCopyRecovery

router = APIRouter()


@router.get("/operations/recoveries")
async def list_recoveries(
    status: str = Query("", description="Filter by status (e.g. failed_retryable, retried_success)"),
    recovery_type: str = Query("", description="open_recovery | close_recovery"),
    limit: int = Query(200, ge=1, le=1000),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Return latest recovery attempts with user/account details for the Operations panel."""
    # Use raw SQL to join user/email + mt5 login (avoid model coupling churn)
    sql = """
        SELECT
            r.id, r.order_id, r.symbol, r.action, r.direction, r.volume,
            r.master_ticket, r.client_ticket, r.recovery_type,
            r.attempt_number, r.max_attempts, r.decision, r.reason_code, r.status,
            r.original_price, r.current_price, r.price_delta_points,
            r.mt5_retcode, r.mt5_retcode_comment, r.error_message,
            r.decided_at, r.executed_at,
            r.mt5_account_id, r.user_id,
            u.email AS user_email,
            ma.login AS account_login,
            ma.server AS account_server
        FROM trade_copy_recoveries r
        LEFT JOIN users u ON u.id = r.user_id
        LEFT JOIN mt5_accounts ma ON ma.id = r.mt5_account_id
        WHERE 1=1
    """
    params: dict = {}
    if status:
        sql += " AND r.status = :status"
        params["status"] = status
    if recovery_type:
        sql += " AND r.recovery_type = :rtype"
        params["rtype"] = recovery_type
    sql += " ORDER BY r.decided_at DESC LIMIT :limit"
    params["limit"] = limit

    result = await db.execute(text(sql), params)
    rows = result.fetchall()

    return [
        {
            "id": str(r.id),
            "order_id": r.order_id,
            "symbol": r.symbol,
            "action": r.action,
            "direction": r.direction,
            "volume": float(r.volume),
            "master_ticket": int(r.master_ticket),
            "client_ticket": int(r.client_ticket) if r.client_ticket else None,
            "recovery_type": r.recovery_type,
            "attempt_number": int(r.attempt_number),
            "max_attempts": int(r.max_attempts),
            "decision": r.decision,
            "reason_code": r.reason_code,
            "status": r.status,
            "original_price": float(r.original_price) if r.original_price is not None else None,
            "current_price": float(r.current_price) if r.current_price is not None else None,
            "price_delta_points": float(r.price_delta_points) if r.price_delta_points is not None else None,
            "mt5_retcode": int(r.mt5_retcode) if r.mt5_retcode is not None else None,
            "mt5_retcode_comment": r.mt5_retcode_comment,
            "error_message": r.error_message,
            "decided_at": r.decided_at.isoformat() if r.decided_at else None,
            "executed_at": r.executed_at.isoformat() if r.executed_at else None,
            "mt5_account_id": str(r.mt5_account_id),
            "user_id": str(r.user_id) if r.user_id else None,
            "user_email": r.user_email,
            "account_login": int(r.account_login) if r.account_login else None,
            "account_server": r.account_server,
        }
        for r in rows
    ]


@router.get("/operations/recoveries/summary")
async def recoveries_summary(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Compact KPIs for the Operations panel header."""
    sql = """
        SELECT
            COUNT(*) FILTER (WHERE status = 'failed_retryable')          AS reprocessing,
            COUNT(*) FILTER (WHERE status = 'retried_success')           AS retried_success,
            COUNT(*) FILTER (WHERE status = 'retried_rejected')          AS retried_rejected,
            COUNT(*) FILTER (WHERE status = 'close_retrying')            AS close_retrying,
            COUNT(*) FILTER (WHERE status = 'close_retry_success')       AS close_retry_success,
            COUNT(*) FILTER (WHERE status = 'close_retry_failed')        AS close_retry_failed,
            COUNT(*) FILTER (WHERE status = 'no_position_to_close')      AS no_position,
            COUNT(*) FILTER (WHERE decided_at >= now() - interval '24 hours') AS last_24h
        FROM trade_copy_recoveries
        WHERE decided_at >= now() - interval '7 days'
    """
    res = await db.execute(text(sql))
    row = res.fetchone()
    return {
        "reprocessing": int(row.reprocessing or 0),
        "retried_success": int(row.retried_success or 0),
        "retried_rejected": int(row.retried_rejected or 0),
        "close_retrying": int(row.close_retrying or 0),
        "close_retry_success": int(row.close_retry_success or 0),
        "close_retry_failed": int(row.close_retry_failed or 0),
        "no_position": int(row.no_position or 0),
        "last_24h": int(row.last_24h or 0),
    }
