"""Tests for the Bridge Auditor service (pure logic — no DB / no Redis)."""

import os
import uuid
import pytest

os.environ["BRIDGE_AUDITOR_ENABLED"] = "true"

from app.services.bridge_auditor_service import position_is_ours, _execution_magic
from app.models import bridge_audit as A


def _execution_magic_for(order_id):
    return _execution_magic(order_id)


def test_position_is_ours_by_magic():
    oid = uuid.uuid4()
    magic = _execution_magic_for(oid)
    pos = {"magic": magic, "comment": ""}
    assert position_is_ours(pos, expected_magic=magic, master_ticket=None) is True


def test_position_is_ours_by_master_ticket_in_comment():
    oid = uuid.uuid4()
    magic = _execution_magic_for(oid)
    pos = {"magic": 0, "comment": "ctp: master_ticket=987654 strategy=low"}
    assert position_is_ours(pos, expected_magic=magic, master_ticket="987654") is True


def test_position_is_NOT_ours_when_no_link():
    oid = uuid.uuid4()
    magic = _execution_magic_for(oid)
    pos = {"magic": 1234, "comment": "manual entry"}
    assert position_is_ours(pos, expected_magic=magic, master_ticket="999") is False


def test_position_is_NOT_ours_when_position_missing():
    assert position_is_ours(None, expected_magic=1, master_ticket=None) is False


# ── Status constants exist as documented ────────────────────────────────────
def test_audit_statuses_present():
    for s in ("pending", "matched", "not_executed", "wrong_lot", "wrong_symbol",
              "wrong_direction", "sl_tp_mismatch", "already_closed",
              "orphan_position_found", "auto_fixed", "auto_fix_failed",
              "failed_to_check", "still_open"):
        assert any(getattr(A, k) == s for k in dir(A) if k.startswith("AUDIT_"))


# ── Auto-fix gating (mock-style: just exercise flag logic without DB) ───────
class _Cfg:
    BRIDGE_AUDITOR_AUTO_FIX_ENABLED = False
    BRIDGE_AUDITOR_CLOSE_ORPHAN_POSITIONS = True


def test_auto_fix_disabled_does_not_enqueue(monkeypatch):
    """If auto-fix is off, still_open must NOT trigger any fix enqueue."""
    from app.services import bridge_auditor_service as svc
    monkeypatch.setattr(svc, "get_auditor_settings", lambda: _Cfg())

    enq_called = []

    async def fake_enqueue(*a, **kw):
        enq_called.append((a, kw))

    monkeypatch.setattr(svc, "_enqueue_fix", fake_enqueue)

    class FakeAudit:
        bridge_execution_order_id = uuid.uuid4()
        master_ticket = "1"
        expected_sl = None
        expected_tp = None
        expected_symbol = "XAUUSD"
        client_login = "1"
        mt5_account_id = uuid.uuid4()
        id = uuid.uuid4()
        audit_status = ""
        detected_status = ""
        failure_reason = ""
        checked_at = None
        auto_fix_attempted = False

    import asyncio
    audit = FakeAudit()
    asyncio.run(svc.apply_check_result(None, audit, {
        "status": "still_open", "reason": "x",
        "position": {"magic": _execution_magic(audit.bridge_execution_order_id)},
    }))
    assert audit.audit_status == A.AUDIT_STILL_OPEN
    assert enq_called == []
