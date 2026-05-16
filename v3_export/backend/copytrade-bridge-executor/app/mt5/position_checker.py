"""Check positions for the auditor."""
from __future__ import annotations

from typing import Optional

from app.config import settings


def _is_ours(position) -> bool:
    if position.magic == settings.order_magic:
        return True
    return (position.comment or "").startswith(f"{settings.order_comment_prefix}:")


def find_by_execution(mt5, execution_order_id: str, master_ticket: Optional[str] = None,
                     symbol: Optional[str] = None):
    positions = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
    positions = positions or []
    for p in positions:
        if not _is_ours(p):
            continue
        c = p.comment or ""
        if execution_order_id and execution_order_id in c:
            return p
        if master_ticket and master_ticket in c:
            return p
    return None
