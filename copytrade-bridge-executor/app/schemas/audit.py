"""Auditor payloads."""
from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel


AuditCommand = Literal["CHECK_POSITION", "CHECK_CLOSED", "FORCE_CLOSE", "FORCE_MODIFY_SL_TP"]
AuditStatus = Literal[
    "matched",
    "not_found",
    "still_open",
    "wrong_direction",
    "wrong_lot",
    "wrong_symbol",
    "auto_fixed",
    "auto_fix_failed",
    "skipped_not_ours",
    "error",
]


class AuditRequest(BaseModel):
    audit_id: Optional[str] = None
    execution_order_id: str
    client_login: str
    client_server: Optional[str] = None
    client_password: Optional[str] = None
    command: AuditCommand
    symbol: Optional[str] = None
    expected_lot: Optional[float] = None
    expected_direction: Optional[str] = None
    master_ticket: Optional[str] = None
    sl: Optional[float] = None
    tp: Optional[float] = None


class AuditResult(BaseModel):
    audit_id: Optional[str] = None
    execution_order_id: str
    executor_id: str
    client_login: str
    command: AuditCommand
    status: AuditStatus
    message: str = ""
    payload: dict = {}
    checked_at: str
