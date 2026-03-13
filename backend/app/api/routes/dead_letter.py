"""Admin dead-letter queue management endpoints."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from app.core.database import get_db
from app.api.deps import require_admin
from app.models.user import User
from app.models.dead_letter import DeadLetterTrade, DeadLetterStatus

router = APIRouter()


@router.get("/dead-letter")
async def list_dead_letter_trades(
    status: str = Query("", description="Filter by status: pending, retried, resolved"),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    query = select(DeadLetterTrade).order_by(desc(DeadLetterTrade.created_at))
    if status:
        query = query.where(DeadLetterTrade.status == DeadLetterStatus(status))
    result = await db.execute(query.limit(200))
    trades = result.scalars().all()

    return [
        {
            "id": str(t.id),
            "order_id": t.order_id,
            "symbol": t.symbol,
            "action": t.action,
            "direction": t.direction,
            "volume": t.volume,
            "master_ticket": t.master_ticket,
            "client_mt5_id": t.client_mt5_id,
            "error_message": t.error_message,
            "attempt_count": t.attempt_count,
            "status": t.status.value,
            "resolution_note": t.resolution_note,
            "created_at": t.created_at.isoformat(),
            "resolved_at": t.resolved_at.isoformat() if t.resolved_at else None,
        }
        for t in trades
    ]


@router.post("/dead-letter/{trade_id}/retry")
async def retry_dead_letter_trade(
    trade_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Re-enqueue a failed trade for execution."""
    result = await db.execute(select(DeadLetterTrade).where(DeadLetterTrade.id == trade_id))
    trade = result.scalar_one_or_none()
    if not trade:
        raise HTTPException(status_code=404, detail="Dead letter trade not found")
    if trade.status != DeadLetterStatus.PENDING:
        raise HTTPException(status_code=400, detail="Trade is not in pending status")

    # Re-enqueue to Redis
    try:
        import redis as redis_lib
        from app.core.config import get_settings
        r = redis_lib.from_url(get_settings().REDIS_URL)
        queue_key = f"copytrade:execute:{trade.client_mt5_id}"
        r.lpush(queue_key, trade.raw_payload)
        trade.status = DeadLetterStatus.RETRIED
        trade.attempt_count += 1
        await db.commit()
        return {"message": f"Trade {trade.order_id} re-enqueued for execution"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to re-enqueue: {str(e)}")


@router.post("/dead-letter/{trade_id}/resolve")
async def resolve_dead_letter_trade(
    trade_id: str,
    note: str = "",
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Mark a dead letter trade as resolved."""
    result = await db.execute(select(DeadLetterTrade).where(DeadLetterTrade.id == trade_id))
    trade = result.scalar_one_or_none()
    if not trade:
        raise HTTPException(status_code=404, detail="Dead letter trade not found")

    trade.status = DeadLetterStatus.RESOLVED
    trade.resolution_note = note or "Manually resolved by admin"
    trade.resolved_at = datetime.now(timezone.utc)
    await db.commit()
    return {"message": f"Trade {trade.order_id} marked as resolved"}
