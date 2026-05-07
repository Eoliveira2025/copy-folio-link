"""Bridge Auditor worker.

Two responsibilities:

1. SCAN executed `bridge_execution_orders` (status = 'executed') without an audit yet,
   and create a `bridge_audits` row + enqueue the check on Redis after a delay.
2. CONSUME executor responses from Redis lists:
     - `bridge:audit:result` (check responses)
     - `bridge:audit:fix:result` (corrective action responses)
   and update the corresponding `bridge_audits` row.

Run: `python -m app.workers.bridge_auditor`
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from app.core.config import get_settings
from app.core.bridge_auditor_config import get_auditor_settings
from app.core.database import AsyncSessionLocal
from app.models.bridge import BridgeExecutionOrder
from app.models.bridge_audit import BridgeAudit, AUDIT_PENDING
from app.services.bridge_auditor_service import (
    create_audit_for_executed_order,
    apply_check_result,
    apply_fix_result,
)

RESULT_QUEUE = "bridge:audit:result"
FIX_RESULT_QUEUE = "bridge:audit:fix:result"

logger = logging.getLogger("bridge.auditor.worker")
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(name)s] %(levelname)s %(message)s")


async def _scan_loop() -> None:
    cfg = get_auditor_settings()
    while True:
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(seconds=cfg.BRIDGE_AUDITOR_DELAY_SECONDS)
            async with AsyncSessionLocal() as db:
                rows = (await db.execute(
                    text("""
                        SELECT eo.* FROM bridge_execution_orders eo
                        WHERE eo.status = 'executed'
                          AND eo.executed_at <= :cutoff
                          AND NOT EXISTS (
                            SELECT 1 FROM bridge_audits a
                             WHERE a.bridge_execution_order_id = eo.id
                          )
                        ORDER BY eo.executed_at ASC
                        LIMIT 200
                    """),
                    {"cutoff": cutoff},
                )).fetchall()
                for r in rows:
                    order = (await db.execute(
                        select(BridgeExecutionOrder).where(BridgeExecutionOrder.id == r.id)
                    )).scalar_one()
                    await create_audit_for_executed_order(db, order)
                if rows:
                    await db.commit()
                    logger.info("created %d new audits", len(rows))
        except Exception as e:
            logger.exception("scan_loop error: %s", e)
        await asyncio.sleep(max(1, cfg.BRIDGE_AUDITOR_DELAY_SECONDS))


async def _result_loop() -> None:
    redis = aioredis.from_url(get_settings().REDIS_URL, decode_responses=True)
    while True:
        try:
            msg = await redis.blpop([RESULT_QUEUE, FIX_RESULT_QUEUE], timeout=5)
            if not msg:
                continue
            queue_name, raw = msg
            try:
                payload = json.loads(raw)
            except Exception:
                logger.warning("invalid payload on %s: %s", queue_name, raw)
                continue
            audit_id = payload.get("audit_id")
            if not audit_id:
                continue
            async with AsyncSessionLocal() as db:
                audit = (await db.execute(
                    select(BridgeAudit).where(BridgeAudit.id == uuid.UUID(audit_id))
                )).scalar_one_or_none()
                if not audit:
                    logger.warning("audit %s not found", audit_id)
                    continue
                if queue_name == RESULT_QUEUE:
                    await apply_check_result(db, audit, payload)
                else:
                    await apply_fix_result(db, audit, payload)
                await db.commit()
        except Exception as e:
            logger.exception("result_loop error: %s", e)


async def main() -> None:
    cfg = get_auditor_settings()
    if not cfg.BRIDGE_AUDITOR_ENABLED:
        logger.warning("BRIDGE_AUDITOR_ENABLED=false — auditor exiting")
        return
    logger.info("Bridge Auditor started. auto_fix=%s close_orphans=%s",
                cfg.BRIDGE_AUDITOR_AUTO_FIX_ENABLED,
                cfg.BRIDGE_AUDITOR_CLOSE_ORPHAN_POSITIONS)
    await asyncio.gather(_scan_loop(), _result_loop())


if __name__ == "__main__":
    asyncio.run(main())
