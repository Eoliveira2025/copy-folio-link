"""Bridge service: persist incoming signals and publish to Redis."""

import json
import logging
import uuid
from typing import Any

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.bridge_config import get_bridge_settings
from app.core.config import get_settings
from app.models.bridge import BridgeSignal
from app.schemas.bridge import BridgeSignalIn

logger = logging.getLogger("app.bridge")

_redis: aioredis.Redis | None = None


def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(get_settings().REDIS_URL, decode_responses=True)
    return _redis


async def ingest_signal(db: AsyncSession, payload: BridgeSignalIn) -> BridgeSignal:
    cfg = get_bridge_settings()
    signal = BridgeSignal(
        master_id=payload.master_id,
        strategy_id=payload.strategy_id,
        action=payload.action,
        symbol=payload.symbol,
        master_ticket=payload.master_ticket,
        position_id=payload.position_id,
        order_type=payload.order_type,
        volume=payload.volume,
        price=payload.price,
        sl=payload.sl,
        tp=payload.tp,
        master_balance=payload.master_balance,
        raw_payload=payload.model_dump(mode="json"),
        status="received",
    )
    db.add(signal)
    await db.flush()

    channel = f"{cfg.BRIDGE_REDIS_CHANNEL_PREFIX}:{payload.master_id}"
    try:
        r = _get_redis()
        await r.publish(channel, json.dumps({"signal_id": str(signal.id), **signal.raw_payload}))
    except Exception as e:  # never fail the ingestion if Redis is unavailable
        logger.warning("Bridge redis publish failed: %s", e)
        signal.error_message = f"redis_publish_failed: {e}"

    return signal
