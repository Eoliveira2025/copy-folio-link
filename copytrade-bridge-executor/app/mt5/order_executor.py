"""Execute OPEN / CLOSE / MODIFY orders on MT5."""
from __future__ import annotations

from typing import Optional

from app.config import settings
from app.mt5 import symbol_resolver
from app.schemas.execution import ExecutionOrder
from app.utils.logger import get_logger

log = get_logger("mt5.exec")


def _comment(order: ExecutionOrder) -> str:
    return f"{settings.order_comment_prefix}:{order.execution_order_id}:{order.master_ticket or ''}"


def _is_ours(position) -> bool:
    if position.magic == settings.order_magic:
        return True
    c = (position.comment or "")
    return c.startswith(f"{settings.order_comment_prefix}:")


def find_position(mt5, order: ExecutionOrder):
    """Find a position created by the executor for this execution_order_id."""
    positions = mt5.positions_get(symbol=symbol_resolver.resolve(order.symbol)) or []
    eo = order.execution_order_id
    mt = order.master_ticket or ""
    for p in positions:
        if not _is_ours(p):
            continue
        c = p.comment or ""
        if eo in c or (mt and mt in c) or p.magic == settings.order_magic:
            # prefer exact execution_order_id match
            if eo and eo in c:
                return p
    # fallback: any of ours with master_ticket in comment
    for p in positions:
        if _is_ours(p) and mt and mt in (p.comment or ""):
            return p
    return None


def execute_open(mt5, order: ExecutionOrder, symbol: str, lot: float) -> dict:
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        return {"ok": False, "message": "symbol_info_tick None"}

    side = (order.order_type or "BUY").upper()
    if side == "BUY":
        order_type = mt5.ORDER_TYPE_BUY
        price = tick.ask
    elif side == "SELL":
        order_type = mt5.ORDER_TYPE_SELL
        price = tick.bid
    else:
        return {"ok": False, "message": f"order_type {side} not supported in v0.1"}

    req = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": order_type,
        "price": price,
        "sl": order.sl or 0.0,
        "tp": order.tp or 0.0,
        "deviation": settings.default_deviation,
        "magic": settings.order_magic,
        "comment": _comment(order)[:31],
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    res = mt5.order_send(req)
    return _result_dict(res)


def execute_close(mt5, order: ExecutionOrder) -> dict:
    pos = find_position(mt5, order)
    if pos is None:
        return {"ok": False, "message": "already_closed_or_not_found"}

    if not _is_ours(pos):
        return {"ok": False, "message": "skipped_not_ours"}

    symbol = pos.symbol
    tick = mt5.symbol_info_tick(symbol)
    close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
    price = tick.bid if pos.type == mt5.POSITION_TYPE_BUY else tick.ask
    req = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "position": pos.ticket,
        "volume": pos.volume,
        "type": close_type,
        "price": price,
        "deviation": settings.default_deviation,
        "magic": settings.order_magic,
        "comment": (_comment(order) + ":CLOSE")[:31],
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    res = mt5.order_send(req)
    return _result_dict(res, position_ticket=pos.ticket)


def execute_modify(mt5, order: ExecutionOrder) -> dict:
    pos = find_position(mt5, order)
    if pos is None:
        return {"ok": False, "message": "position_not_found"}
    if not _is_ours(pos):
        return {"ok": False, "message": "skipped_not_ours"}
    req = {
        "action": mt5.TRADE_ACTION_SLTP,
        "symbol": pos.symbol,
        "position": pos.ticket,
        "sl": order.sl or 0.0,
        "tp": order.tp or 0.0,
    }
    res = mt5.order_send(req)
    return _result_dict(res, position_ticket=pos.ticket)


def _result_dict(res, position_ticket: Optional[int] = None) -> dict:
    if res is None:
        return {"ok": False, "message": "order_send returned None"}
    ok = res.retcode in (10009, 10008)  # DONE / PLACED
    return {
        "ok": ok,
        "retcode": int(res.retcode),
        "message": getattr(res, "comment", "") or ("ok" if ok else "failed"),
        "mt5_order": str(getattr(res, "order", "") or ""),
        "mt5_position": str(position_ticket or getattr(res, "position", "") or ""),
    }
