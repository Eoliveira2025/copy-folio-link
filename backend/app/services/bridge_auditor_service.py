"""Bridge Auditor service.

Creates and updates `bridge_audits` rows. Owns the safety rules for any
corrective action (FORCE_CLOSE / FORCE_MODIFY_SL_TP).
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as aioredis
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.bridge_auditor_config import get_auditor_settings
from app.models.bridge import BridgeExecutionOrder
from app.models.bridge_audit import (
    BridgeAudit,
    AUDIT_PENDING,
    AUDIT_MATCHED,
    AUDIT_NOT_EXECUTED,
    AUDIT_WRONG_LOT,
    AUDIT_WRONG_DIRECTION,
    AUDIT_WRONG_SYMBOL,
    AUDIT_SLTP_MISMATCH,
    AUDIT_ALREADY_CLOSED,
    AUDIT_STILL_OPEN,
    AUDIT_AUTO_FIXED,
    AUDIT_AUTO_FIX_FAILED,
    AUDIT_FAILED_TO_CHECK,
)

logger = logging.getLogger("bridge.auditor")

CHECK_QUEUE_PREFIX = "bridge:audit:check"
FIX_QUEUE_PREFIX = "bridge:audit:fix"
PENDING_QUEUE = "bridge:audit:pending"


def _redis() -> aioredis.Redis:
    return aioredis.from_url(get_settings().REDIS_URL, decode_responses=True)


def _execution_magic(order_id: uuid.UUID) -> int:
    """Stable magic number derived from execution_order_id (positive 31-bit)."""
    return int(order_id.int & 0x7FFFFFFF)


# ── Safety: verify a position is owned by CopyTrade Pro before any corrective action ──
def position_is_ours(position: dict[str, Any] | None, *, expected_magic: int,
                     master_ticket: str | None) -> bool:
    if not position:
        return False
    magic = position.get("magic")
    comment = (position.get("comment") or "").lower()
    if magic is not None and int(magic) == int(expected_magic):
        return True
    if master_ticket and master_ticket.lower() in comment:
        return True
    if "copytradepro" in comment or "ctp:" in comment:
        return True
    return False


async def create_audit_for_executed_order(db: AsyncSession,
                                          order: BridgeExecutionOrder) -> BridgeAudit:
    audit = BridgeAudit(
        bridge_execution_order_id=order.id,
        bridge_signal_id=order.bridge_signal_id,
        user_id=order.user_id,
        mt5_account_id=order.mt5_account_id,
        client_login=order.client_login,
        expected_action=order.action,
        expected_symbol=order.symbol,
        expected_order_type=order.order_type,
        expected_lot=order.calculated_lot,
        expected_sl=order.sl,
        expected_tp=order.tp,
        master_ticket=None,  # filled by signal join below
        audit_status=AUDIT_PENDING,
    )
    # Pull master_ticket from signal
    sig_row = (await db.execute(
        text("SELECT master_ticket FROM bridge_signals WHERE id = :sid"),
        {"sid": order.bridge_signal_id},
    )).fetchone()
    if sig_row:
        audit.master_ticket = sig_row.master_ticket
    db.add(audit)
    await db.flush()
    await enqueue_check(audit, order)
    return audit


async def enqueue_check(audit: BridgeAudit, order: BridgeExecutionOrder) -> None:
    """Push payload to the per-client check queue and signal the pending list."""
    if order.action == "OPEN":
        check_action = "CHECK_POSITION"
    elif order.action == "CLOSE":
        check_action = "CHECK_CLOSED"
    elif order.action in ("MODIFY", "SLTP"):
        check_action = "CHECK_SL_TP"
    else:
        check_action = "CHECK_POSITION"

    payload = {
        "audit_id": str(audit.id),
        "execution_order_id": str(order.id),
        "client_login": audit.client_login,
        "mt5_account_id": str(audit.mt5_account_id),
        "action": check_action,
        "symbol": audit.expected_symbol,
        "expected_order_type": audit.expected_order_type,
        "expected_lot": float(audit.expected_lot) if audit.expected_lot is not None else None,
        "expected_sl": float(audit.expected_sl) if audit.expected_sl is not None else None,
        "expected_tp": float(audit.expected_tp) if audit.expected_tp is not None else None,
        "master_ticket": audit.master_ticket,
        "execution_magic": _execution_magic(order.id),
    }
    audit.raw_check_payload = payload
    try:
        r = _redis()
        await r.rpush(f"{CHECK_QUEUE_PREFIX}:{audit.client_login}", json.dumps(payload))
        await r.rpush(PENDING_QUEUE, str(audit.id))
    except Exception as e:
        logger.warning("auditor enqueue failed: %s", e)


# ── Result handling ───────────────────────────────────────────────────────────
async def apply_check_result(db: AsyncSession, audit: BridgeAudit,
                             result: dict[str, Any]) -> None:
    cfg = get_auditor_settings()
    status = (result.get("status") or "error").lower()
    reason = result.get("reason") or ""
    position = result.get("position")
    audit.detected_status = status
    audit.checked_at = datetime.now(timezone.utc)

    if status == "matched":
        audit.audit_status = AUDIT_MATCHED
        return
    if status == "already_closed":
        audit.audit_status = AUDIT_ALREADY_CLOSED
        return
    if status == "wrong_lot":
        audit.audit_status = AUDIT_WRONG_LOT
        audit.failure_reason = reason
        return
    if status == "wrong_symbol":
        audit.audit_status = AUDIT_WRONG_SYMBOL
        audit.failure_reason = reason
        return
    if status == "wrong_direction":
        audit.audit_status = AUDIT_WRONG_DIRECTION
        audit.failure_reason = reason
        return
    if status == "sl_tp_mismatch":
        audit.audit_status = AUDIT_SLTP_MISMATCH
        audit.failure_reason = reason
        if cfg.BRIDGE_AUDITOR_AUTO_FIX_ENABLED:
            await _enqueue_fix(audit, action="FORCE_MODIFY_SL_TP",
                               reason="SL/TP divergence detected by auditor")
        return
    if status == "not_found":
        audit.audit_status = AUDIT_NOT_EXECUTED
        audit.failure_reason = reason or "Position not present in client account"
        return
    if status == "still_open":
        # CLOSE expected but position is still open
        audit.audit_status = AUDIT_STILL_OPEN
        audit.failure_reason = reason or "Master closed but client still open"
        # ── Safety gate ──
        if not cfg.BRIDGE_AUDITOR_AUTO_FIX_ENABLED:
            return
        if not cfg.BRIDGE_AUDITOR_CLOSE_ORPHAN_POSITIONS:
            return
        magic_expected = _execution_magic(audit.bridge_execution_order_id)
        if not position_is_ours(position, expected_magic=magic_expected,
                                master_ticket=audit.master_ticket):
            audit.failure_reason = (
                (audit.failure_reason or "") +
                " | refused to auto-close: position has no CopyTrade Pro magic/comment link"
            )
            return
        await _enqueue_fix(audit, action="FORCE_CLOSE",
                           reason="Master position already closed but client still open")
        return
    if status == "error":
        audit.audit_status = AUDIT_FAILED_TO_CHECK
        audit.failure_reason = reason or "executor error"
        return

    audit.audit_status = AUDIT_FAILED_TO_CHECK
    audit.failure_reason = f"unknown status: {status}"


async def _enqueue_fix(audit: BridgeAudit, *, action: str, reason: str) -> None:
    payload = {
        "audit_id": str(audit.id),
        "execution_order_id": str(audit.bridge_execution_order_id),
        "client_login": audit.client_login,
        "mt5_account_id": str(audit.mt5_account_id),
        "action": action,
        "symbol": audit.expected_symbol,
        "master_ticket": audit.master_ticket,
        "expected_sl": float(audit.expected_sl) if audit.expected_sl is not None else None,
        "expected_tp": float(audit.expected_tp) if audit.expected_tp is not None else None,
        "reason": reason,
    }
    audit.auto_fix_attempted = True
    try:
        r = _redis()
        await r.rpush(f"{FIX_QUEUE_PREFIX}:{audit.client_login}", json.dumps(payload))
    except Exception as e:
        audit.audit_status = AUDIT_AUTO_FIX_FAILED
        audit.auto_fix_result = {"error": str(e)}


async def apply_fix_result(db: AsyncSession, audit: BridgeAudit, result: dict[str, Any]) -> None:
    audit.auto_fix_result = result
    audit.checked_at = datetime.now(timezone.utc)
    if (result.get("status") or "").lower() in ("matched", "already_closed", "fixed", "ok"):
        audit.audit_status = AUDIT_AUTO_FIXED
    else:
        audit.audit_status = AUDIT_AUTO_FIX_FAILED
        audit.failure_reason = (audit.failure_reason or "") + \
            f" | auto-fix failed: {result.get('reason', 'unknown')}"
