"""Bridge Distributor worker.

Subscribes to Redis `bridge:signal:*`, computes proportional lot sizes for every
eligible client of the master/strategy, persists `bridge_execution_orders` and
enqueues each order to `bridge:execute:{client_login}` for the Windows Executor
to consume.

Run: `python -m app.workers.bridge_distributor`
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import uuid
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as aioredis
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.core.bridge_config import get_bridge_settings
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.models.bridge import BridgeExecutionOrder, BridgeSignal
from app.models.mt5_account import MT5Account, MT5Status
from app.models.subscription import AccessStatus, Subscription, SubscriptionStatus
from app.models.strategy import Strategy, UserStrategy

logger = logging.getLogger("bridge.distributor")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")


def normalize_lot(raw: float, *, min_lot: float, max_lot: float, step: float) -> float:
    if raw <= 0:
        return 0.0
    steps = math.floor(raw / step)
    snapped = round(steps * step, 8)
    if snapped < min_lot:
        return 0.0
    return min(snapped, max_lot)


def calc_proportional(master_volume: float, master_balance: float, client_balance: float, risk: float) -> float:
    if master_volume <= 0 or master_balance <= 0 or client_balance <= 0:
        return 0.0
    return master_volume * (client_balance / master_balance) * risk


async def _resolve_strategy(db, master_id: str, strategy_id: str | None) -> Strategy | None:
    if strategy_id:
        try:
            sid = uuid.UUID(strategy_id)
        except ValueError:
            sid = None
        if sid:
            r = await db.execute(select(Strategy).where(Strategy.id == sid))
            s = r.scalar_one_or_none()
            if s:
                return s
    # fallback by level == master_id (e.g. "low", "medium" …)
    r = await db.execute(select(Strategy).where(Strategy.level == master_id))
    return r.scalar_one_or_none()


async def _eligible_clients(db, strategy: Strategy):
    """Return tuples of (user_id, mt5_account, client_balance, risk_multiplier)."""
    cfg = get_bridge_settings()
    sql = text(
        """
        SELECT u.id AS user_id, ma.id AS mt5_id, ma.login AS mt5_login,
               ma.balance AS mt5_balance, s.status AS sub_status,
               s.access_status AS access_status
        FROM user_strategies us
        JOIN users u ON u.id = us.user_id AND u.is_active = TRUE
        JOIN mt5_accounts ma ON ma.user_id = u.id AND ma.status = :connected
        LEFT JOIN subscriptions s ON s.user_id = u.id
        WHERE us.strategy_id = :sid AND us.is_active = TRUE
        """
    )
    rows = (await db.execute(sql, {"sid": strategy.id, "connected": MT5Status.CONNECTED.value})).fetchall()
    out = []
    for row in rows:
        if cfg.BRIDGE_REQUIRE_ACTIVE_SUBSCRIPTION:
            if row.sub_status not in (SubscriptionStatus.TRIAL.value, SubscriptionStatus.ACTIVE.value):
                continue
            if row.access_status == AccessStatus.BLOCKED.value:
                continue
        out.append(row)
    return out


async def process_signal(payload: dict[str, Any]) -> None:
    cfg = get_bridge_settings()
    signal_id = payload.get("signal_id")
    if not signal_id:
        return

    async with AsyncSessionLocal() as db:
        sig = (await db.execute(select(BridgeSignal).where(BridgeSignal.id == uuid.UUID(signal_id)))).scalar_one_or_none()
        if not sig:
            logger.warning("Signal %s not found", signal_id)
            return

        strategy = await _resolve_strategy(db, sig.master_id, sig.strategy_id)
        if not strategy:
            sig.status = "no_strategy"
            sig.error_message = f"no strategy for master={sig.master_id}"
            sig.processed_at = datetime.now(timezone.utc)
            await db.commit()
            return

        clients = await _eligible_clients(db, strategy)
        master_balance = float(sig.master_balance or 0) or 1.0
        risk = float(getattr(strategy, "risk_multiplier", 1.0) or 1.0)
        master_vol = float(sig.volume)

        r = aioredis.from_url(get_settings().REDIS_URL, decode_responses=True)
        created = 0
        for c in clients:
            client_balance = float(c.mt5_balance or 0)
            raw_lot = calc_proportional(master_vol, master_balance, client_balance, risk)
            lot = normalize_lot(
                raw_lot,
                min_lot=cfg.BRIDGE_MIN_LOT,
                max_lot=cfg.BRIDGE_MAX_LOT,
                step=cfg.BRIDGE_DEFAULT_LOT_STEP,
            )
            queue = f"{cfg.BRIDGE_EXECUTE_QUEUE_PREFIX}:{c.mt5_login}"

            status = "queued" if lot > 0 else "skipped_lot_too_small"
            order = BridgeExecutionOrder(
                bridge_signal_id=sig.id,
                user_id=c.user_id,
                mt5_account_id=c.mt5_id,
                client_login=str(c.mt5_login),
                symbol=sig.symbol,
                action=sig.action,
                order_type=sig.order_type,
                calculated_lot=lot,
                price=sig.price,
                sl=sig.sl,
                tp=sig.tp,
                status=status,
                redis_queue=queue,
            )
            db.add(order)
            try:
                await db.flush()
            except IntegrityError:
                await db.rollback()
                continue  # idempotency hit

            if status == "queued":
                msg = {
                    "execution_order_id": str(order.id),
                    "client_login": str(c.mt5_login),
                    "mt5_account_id": str(c.mt5_id),
                    "action": sig.action,
                    "symbol": sig.symbol,
                    "order_type": sig.order_type,
                    "lot": float(lot),
                    "price": float(sig.price) if sig.price is not None else None,
                    "sl": float(sig.sl) if sig.sl is not None else None,
                    "tp": float(sig.tp) if sig.tp is not None else None,
                    "master_ticket": sig.master_ticket,
                    "strategy_id": str(strategy.id),
                }
                try:
                    await r.rpush(queue, json.dumps(msg))
                    created += 1
                except Exception as e:
                    logger.error("Enqueue failed for %s: %s", queue, e)
                    order.status = "enqueue_failed"
                    order.error_message = str(e)

        sig.status = "distributed"
        sig.processed_at = datetime.now(timezone.utc)
        await db.commit()
        logger.info("signal %s → %d orders enqueued", signal_id, created)


async def main() -> None:
    cfg = get_bridge_settings()
    if not cfg.BRIDGE_ENABLED:
        logger.warning("BRIDGE_ENABLED=false — distributor exiting")
        return
    redis = aioredis.from_url(get_settings().REDIS_URL, decode_responses=True)
    pubsub = redis.pubsub()
    pattern = f"{cfg.BRIDGE_REDIS_CHANNEL_PREFIX}:*"
    await pubsub.psubscribe(pattern)
    logger.info("Bridge distributor listening on %s", pattern)

    async for message in pubsub.listen():
        if message.get("type") != "pmessage":
            continue
        try:
            payload = json.loads(message["data"])
        except Exception as e:
            logger.warning("invalid payload: %s", e)
            continue
        try:
            await process_signal(payload)
        except Exception as e:
            logger.exception("process_signal error: %s", e)


if __name__ == "__main__":
    asyncio.run(main())
