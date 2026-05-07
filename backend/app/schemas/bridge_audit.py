"""Pydantic schemas for the Bridge Auditor."""

from typing import Literal, Optional, Any
from pydantic import BaseModel, Field


CheckAction = Literal["CHECK_POSITION", "CHECK_CLOSED", "CHECK_SL_TP"]
FixAction = Literal["FORCE_CLOSE", "FORCE_MODIFY_SL_TP"]


class AuditCheckPayload(BaseModel):
    audit_id: str
    execution_order_id: str
    client_login: str
    mt5_account_id: str
    action: CheckAction
    symbol: str
    expected_order_type: Optional[str] = None
    expected_lot: Optional[float] = None
    expected_sl: Optional[float] = None
    expected_tp: Optional[float] = None
    master_ticket: Optional[str] = None
    execution_magic: Optional[int] = None


class AuditFixPayload(BaseModel):
    audit_id: str
    execution_order_id: str
    client_login: str
    mt5_account_id: str
    action: FixAction
    symbol: str
    master_ticket: Optional[str] = None
    expected_sl: Optional[float] = None
    expected_tp: Optional[float] = None
    reason: str


class AuditCheckResult(BaseModel):
    audit_id: str
    status: Literal["matched", "not_found", "still_open", "already_closed", "error",
                    "wrong_lot", "wrong_direction", "wrong_symbol", "sl_tp_mismatch"]
    reason: str = ""
    position: Optional[dict[str, Any]] = None
    checked_at: Optional[str] = None
