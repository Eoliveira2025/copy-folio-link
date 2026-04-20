"""
Copy Recovery Worker

Listens to copytrade:recovery:open and copytrade:recovery:close events,
applies the recovery policy (price-direction for OPEN, retry-up-to-N for CLOSE),
re-enqueues the order if allowed, and records every decision in
`trade_copy_recoveries` for the Admin > Operations panel.

Architecture:
  Executor publishes recovery event on FAILED → this worker decides → either
  re-enqueues a new CopyOrder (with is_recovery=True) on copytrade:execute:{client_id}
  or records a final decision (rejected / fatal / no_position_to_close).

Safe by design:
  - Does NOT interfere with the main distribution path
  - Bounded attempts (open=1, close=3 by default)
  - Idempotent: each attempt is a new audit row keyed by order_id
"""

from __future__ import annotations
import json
import logging
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

import redis
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from engine.config import get_engine_settings
from engine.models import CopyOrder, TradeAction, TradeDirection
from engine.recovery_config import (
    get_recovery_config,
    favorable_limit_for_symbol,
    is_fatal_for_close,
)

settings = get_engine_settings()
logger = logging.getLogger("engine.recovery_worker")

# Redis keys
RECOVERY_OPEN_CHANNEL = "copytrade:recovery:open"
RECOVERY_CLOSE_CHANNEL = "copytrade:recovery:close"
RECOVERY_ATTEMPT_PREFIX = "copytrade:recovery:attempts"  # HSET order_id → count
RECOVERY_LOCK_PREFIX = "copytrade:recovery:lock"
EXECUTE_QUEUE_PREFIX = "copytrade:execute"
TICK_CACHE_PREFIX = "copytrade:tick"


class RecoveryWorker(threading.Thread):
    """Single worker that consumes both OPEN and CLOSE recovery channels."""

    def __init__(self):
        super().__init__(daemon=True, name="RecoveryWorker")
        self.running = False
        self.redis_client: Optional[redis.Redis] = None
        self.db_engine = create_engine(settings.DATABASE_URL_SYNC, pool_size=5, pool_pre_ping=True)
        self._cfg = get_recovery_config()

    # ── Helpers ──────────────────────────────────────────────────

    def _get_attempt_count(self, order_id: str) -> int:
        try:
            v = self.redis_client.hget(RECOVERY_ATTEMPT_PREFIX, order_id)
            return int(v) if v else 0
        except Exception:
            return 0

    def _bump_attempt(self, order_id: str) -> int:
        try:
            n = self.redis_client.hincrby(RECOVERY_ATTEMPT_PREFIX, order_id, 1)
            self.redis_client.expire(RECOVERY_ATTEMPT_PREFIX, 3600)
            return int(n)
        except Exception:
            return 1

    def _current_price(self, client_mt5_id: str, symbol: str, direction: str) -> tuple[Optional[float], Optional[float]]:
        """Return (current_price, point) from executor tick cache; None if unavailable."""
        try:
            raw = self.redis_client.get(f"{TICK_CACHE_PREFIX}:{client_mt5_id}:{symbol}")
            if not raw:
                return None, None
            data = json.loads(raw)
            price = data["ask"] if direction == "BUY" else data["bid"]
            return float(price), float(data.get("point") or 0)
        except Exception:
            return None, None

    def _resolve_user_id(self, client_mt5_id: str) -> Optional[str]:
        try:
            with Session(self.db_engine) as db:
                row = db.execute(
                    text("SELECT user_id FROM mt5_accounts WHERE id = :id"),
                    {"id": client_mt5_id},
                ).fetchone()
                return str(row.user_id) if row else None
        except Exception:
            return None

    def _record(self, **fields):
        """Insert one trade_copy_recoveries row + update trade_copies summary."""
        try:
            with Session(self.db_engine) as db:
                db.execute(
                    text("""
                        INSERT INTO trade_copy_recoveries (
                            id, order_id, mt5_account_id, user_id,
                            symbol, action, direction, volume,
                            master_ticket, client_ticket,
                            recovery_type, attempt_number, max_attempts,
                            decision, reason_code, status,
                            original_price, current_price, price_delta_points,
                            mt5_retcode, mt5_retcode_comment, error_message,
                            decided_at, executed_at
                        ) VALUES (
                            :id, :order_id, :mt5_account_id, :user_id,
                            :symbol, :action, :direction, :volume,
                            :master_ticket, :client_ticket,
                            :recovery_type, :attempt_number, :max_attempts,
                            :decision, :reason_code, :status,
                            :original_price, :current_price, :price_delta_points,
                            :mt5_retcode, :mt5_retcode_comment, :error_message,
                            :decided_at, :executed_at
                        )
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "decided_at": datetime.now(timezone.utc),
                        "executed_at": None,
                        **fields,
                    },
                )
                # Update trade_copies summary (best-effort)
                try:
                    db.execute(text("""
                        UPDATE trade_copies
                           SET retry_attempts = COALESCE(retry_attempts, 0) + 1,
                               recovery_type = :recovery_type,
                               final_status = :status,
                               mt5_retcode = COALESCE(:mt5_retcode, mt5_retcode),
                               mt5_retcode_comment = COALESCE(:mt5_retcode_comment, mt5_retcode_comment),
                               original_price = COALESCE(original_price, :original_price),
                               last_seen_price = COALESCE(:current_price, last_seen_price)
                         WHERE id::text = :order_id
                    """), {
                        "order_id": fields["order_id"],
                        "recovery_type": fields["recovery_type"],
                        "status": fields["status"],
                        "mt5_retcode": fields.get("mt5_retcode"),
                        "mt5_retcode_comment": fields.get("mt5_retcode_comment"),
                        "original_price": fields.get("original_price"),
                        "current_price": fields.get("current_price"),
                    })
                except Exception:
                    pass
                db.commit()
        except Exception as e:
            logger.error(f"Failed to record recovery: {e}", exc_info=True)

    # ── OPEN recovery ───────────────────────────────────────────

    def handle_open(self, payload: dict):
        order_id = payload["order_id"]
        client_mt5_id = payload["client_mt5_account_id"]
        symbol = payload["symbol"]
        direction = payload["direction"]
        original_price = float(payload.get("master_price") or 0)
        max_attempts = self._cfg.max_retry_attempts_open

        attempt = self._bump_attempt(order_id)
        user_id = self._resolve_user_id(client_mt5_id)
        reason_code = payload.get("reason_code") or "unknown_error"

        base_fields = dict(
            order_id=order_id,
            mt5_account_id=client_mt5_id,
            user_id=user_id,
            symbol=symbol,
            action="open",
            direction=direction,
            volume=float(payload["volume"]),
            master_ticket=int(payload["master_ticket"]),
            client_ticket=None,
            recovery_type="open_recovery",
            attempt_number=attempt,
            max_attempts=max_attempts,
            mt5_retcode=payload.get("mt5_retcode"),
            mt5_retcode_comment=payload.get("mt5_retcode_comment"),
            error_message=payload.get("error"),
            original_price=original_price,
        )

        # Window expired?
        detected_at = float(payload.get("event_detected_at") or 0)
        if detected_at and (time.time() - detected_at) > self._cfg.retry_window_seconds_open:
            self._record(
                **base_fields,
                decision="retry_rejected",
                reason_code="retry_window_expired",
                status="retried_rejected",
                current_price=None,
                price_delta_points=None,
            )
            logger.info(f"[recovery] OPEN {order_id[:8]} window expired")
            return

        # Max attempts reached?
        if attempt > max_attempts:
            self._record(
                **base_fields,
                decision="retry_fatal",
                reason_code="retry_failed_final",
                status="retried_rejected",
                current_price=None,
                price_delta_points=None,
            )
            logger.info(f"[recovery] OPEN {order_id[:8]} attempts exhausted")
            return

        # Price decision
        current_price, point = self._current_price(client_mt5_id, symbol, direction)
        favorable_limit = favorable_limit_for_symbol(symbol)

        delta_points = None
        if current_price and original_price > 0 and point and point > 0:
            raw_delta = current_price - original_price
            if direction == "SELL":
                raw_delta = -raw_delta  # favorable for SELL = price went down
            delta_points = raw_delta / point

        # Decision logic:
        # delta_points > 0 = price moved FAVORABLY (against re-entry); reject if exceeds limit
        # delta_points <= 0 = price moved against position; safe to retry
        if delta_points is not None and delta_points > favorable_limit:
            self._record(
                **base_fields,
                decision="retry_rejected",
                reason_code="retry_rejected_favorable_move",
                status="retried_rejected",
                current_price=current_price,
                price_delta_points=delta_points,
            )
            logger.info(
                f"[recovery] OPEN {order_id[:8]} REJECTED favorable move "
                f"{delta_points:.1f}pts > {favorable_limit}pts"
            )
            return

        # Allowed → re-enqueue
        try:
            raw_order_json = payload.get("raw_order")
            if not raw_order_json:
                raise ValueError("missing raw_order in payload")
            order = CopyOrder.from_json(raw_order_json)
            order.order_id = uuid.uuid4().hex  # new id for the retry execution
            order.is_recovery = True
            order.recovery_type = "open_recovery"
            order.recovery_attempt = attempt
            order.recovery_max_attempts = max_attempts
            order.original_master_price = original_price
            # Reset volatile state
            from engine.models import CopyStatus
            order.status = CopyStatus.PENDING
            order.attempt = 0
            order.error = None
            order.mt5_retcode = None
            order.mt5_retcode_comment = None
            order.executed_price = 0.0
            order.executed_at = 0.0
            order.dequeued_at = 0.0

            queue_key = f"{EXECUTE_QUEUE_PREFIX}:{client_mt5_id}"
            self.redis_client.lpush(queue_key, order.to_json())

            self._record(
                **base_fields,
                decision="retry_executed",
                reason_code="retry_success",  # provisional; final result will be in trade_copies
                status="failed_retryable",
                current_price=current_price,
                price_delta_points=delta_points,
            )
            logger.info(
                f"[recovery] OPEN {order_id[:8]} RE-ENQUEUED attempt={attempt} "
                f"delta={delta_points if delta_points is not None else 'n/a'}pts"
            )
        except Exception as e:
            logger.error(f"[recovery] OPEN re-enqueue failed: {e}", exc_info=True)
            self._record(
                **base_fields,
                decision="retry_fatal",
                reason_code="retry_failed_final",
                status="retried_rejected",
                current_price=current_price,
                price_delta_points=delta_points,
                error_message=f"re-enqueue failed: {e}",
            )

    # ── CLOSE recovery ──────────────────────────────────────────

    def handle_close(self, payload: dict):
        order_id = payload["order_id"]
        client_mt5_id = payload["client_mt5_account_id"]
        symbol = payload["symbol"]
        direction = payload["direction"]
        max_attempts = self._cfg.max_retry_attempts_close
        reason_code = payload.get("reason_code") or "unknown_error"
        error_msg = payload.get("error")

        attempt = self._bump_attempt(order_id)
        user_id = self._resolve_user_id(client_mt5_id)

        base_fields = dict(
            order_id=order_id,
            mt5_account_id=client_mt5_id,
            user_id=user_id,
            symbol=symbol,
            action="close",
            direction=direction,
            volume=float(payload["volume"]),
            master_ticket=int(payload["master_ticket"]),
            client_ticket=None,
            recovery_type="close_recovery",
            attempt_number=attempt,
            max_attempts=max_attempts,
            mt5_retcode=payload.get("mt5_retcode"),
            mt5_retcode_comment=payload.get("mt5_retcode_comment"),
            error_message=error_msg,
            original_price=float(payload.get("master_price") or 0) or None,
        )

        # No-position-to-close: detected by error message keywords
        msg_low = (error_msg or "").lower()
        if "no matching client position" in msg_low or "position already closed" in msg_low:
            self._record(
                **base_fields,
                decision="informational",
                reason_code="no_position_to_close",
                status="no_position_to_close",
                current_price=None,
                price_delta_points=None,
                error_message="Posição não encontrada na conta copiadora. Pode ter sido encerrada manualmente pelo usuário.",
            )
            logger.info(f"[recovery] CLOSE {order_id[:8]} no_position_to_close (manual close suspected)")
            return

        # Fatal? Don't retry.
        if is_fatal_for_close(reason_code, error_msg):
            self._record(
                **base_fields,
                decision="retry_fatal",
                reason_code=reason_code,
                status="close_retry_failed",
                current_price=None,
                price_delta_points=None,
            )
            logger.warning(f"[recovery] CLOSE {order_id[:8]} fatal reason={reason_code}")
            return

        # Max attempts?
        if attempt > max_attempts:
            self._record(
                **base_fields,
                decision="retry_fatal",
                reason_code="close_retry_max_attempts_reached",
                status="close_retry_failed",
                current_price=None,
                price_delta_points=None,
            )
            logger.warning(f"[recovery] CLOSE {order_id[:8]} max attempts ({max_attempts}) reached")
            return

        # Re-enqueue (no price gate for CLOSE)
        try:
            raw_order_json = payload.get("raw_order")
            if not raw_order_json:
                raise ValueError("missing raw_order in payload")
            order = CopyOrder.from_json(raw_order_json)
            order.order_id = uuid.uuid4().hex
            order.is_recovery = True
            order.recovery_type = "close_recovery"
            order.recovery_attempt = attempt
            order.recovery_max_attempts = max_attempts
            from engine.models import CopyStatus
            order.status = CopyStatus.PENDING
            order.attempt = 0
            order.error = None
            order.mt5_retcode = None
            order.mt5_retcode_comment = None
            order.executed_at = 0.0
            order.dequeued_at = 0.0

            # Small delay to let any transient market/context clear
            time.sleep(self._cfg.close_retry_delay_ms / 1000.0)

            queue_key = f"{EXECUTE_QUEUE_PREFIX}:{client_mt5_id}"
            self.redis_client.lpush(queue_key, order.to_json())

            self._record(
                **base_fields,
                decision="retry_executed",
                reason_code="close_retrying",
                status="close_retrying",
                current_price=None,
                price_delta_points=None,
            )
            logger.info(f"[recovery] CLOSE {order_id[:8]} RE-ENQUEUED attempt={attempt}/{max_attempts}")
        except Exception as e:
            logger.error(f"[recovery] CLOSE re-enqueue failed: {e}", exc_info=True)
            self._record(
                **base_fields,
                decision="retry_fatal",
                reason_code="close_retry_failed",
                status="close_retry_failed",
                current_price=None,
                price_delta_points=None,
                error_message=f"re-enqueue failed: {e}",
            )

    # ── Main loop ───────────────────────────────────────────────

    def run(self):
        self.running = True
        self.redis_client = redis.Redis.from_url(
            settings.REDIS_URL,
            socket_keepalive=True,
            socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
        )
        logger.info(
            f"Recovery Worker started — open_max={self._cfg.max_retry_attempts_open}, "
            f"close_max={self._cfg.max_retry_attempts_close}"
        )

        while self.running:
            pubsub = None
            try:
                pubsub = self.redis_client.pubsub()
                pubsub.subscribe(RECOVERY_OPEN_CHANNEL, RECOVERY_CLOSE_CHANNEL)

                for message in pubsub.listen():
                    if not self.running:
                        break
                    if message["type"] != "message":
                        continue

                    try:
                        channel = message["channel"]
                        if isinstance(channel, bytes):
                            channel = channel.decode()
                        payload = json.loads(message["data"])
                        if channel == RECOVERY_OPEN_CHANNEL:
                            self.handle_open(payload)
                        elif channel == RECOVERY_CLOSE_CHANNEL:
                            self.handle_close(payload)
                    except Exception as e:
                        logger.error(f"Recovery handler error: {e}", exc_info=True)

            except redis.ConnectionError as e:
                logger.warning(f"Recovery worker Redis lost: {e}, reconnecting in 1s")
                time.sleep(1)
                try:
                    self.redis_client = redis.Redis.from_url(settings.REDIS_URL)
                except Exception:
                    pass
            except Exception as e:
                if self.running:
                    logger.error(f"Recovery worker unexpected: {e}", exc_info=True)
                    time.sleep(1)
            finally:
                if pubsub:
                    try:
                        pubsub.close()
                    except Exception:
                        pass

    def stop(self):
        self.running = False
