"""Run an auditor command on MT5."""
from __future__ import annotations

from datetime import datetime, timezone

from app.config import settings
from app.mt5 import account_session, position_checker, symbol_resolver, terminal_manager
from app.schemas.audit import AuditRequest, AuditResult
from app.utils.logger import get_logger

log = get_logger("svc.audit")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _result(req: AuditRequest, status: str, message: str = "", payload: dict | None = None) -> AuditResult:
    return AuditResult(
        audit_id=req.audit_id,
        execution_order_id=req.execution_order_id,
        executor_id=settings.executor_id,
        client_login=req.client_login,
        command=req.command,
        status=status,  # type: ignore[arg-type]
        message=message,
        payload=payload or {},
        checked_at=_now(),
    )


def run(req: AuditRequest) -> AuditResult:
    if not terminal_manager.is_available():
        return _result(req, "error", "mt5_unavailable")

    try:
        with account_session.login_account(req.client_login, req.client_server, req.client_password) as mt5:
            symbol = symbol_resolver.resolve(req.symbol) if req.symbol else None
            pos = position_checker.find_by_execution(
                mt5, req.execution_order_id, req.master_ticket, symbol
            )

            if req.command == "CHECK_POSITION":
                if pos is None:
                    return _result(req, "not_found")
                problems = []
                if req.expected_lot and abs(pos.volume - req.expected_lot) > 1e-6:
                    problems.append("wrong_lot")
                if req.expected_direction:
                    actual_dir = "BUY" if pos.type == mt5.POSITION_TYPE_BUY else "SELL"
                    if actual_dir != req.expected_direction.upper():
                        problems.append("wrong_direction")
                if req.symbol and symbol and pos.symbol != symbol:
                    problems.append("wrong_symbol")
                if problems:
                    return _result(req, problems[0], ",".join(problems),
                                   {"position": pos.ticket, "volume": pos.volume})
                return _result(req, "matched", payload={"position": pos.ticket, "volume": pos.volume})

            if req.command == "CHECK_CLOSED":
                if pos is None:
                    return _result(req, "matched", "already_closed")
                return _result(req, "still_open", payload={"position": pos.ticket})

            if req.command == "FORCE_CLOSE":
                if pos is None:
                    return _result(req, "matched", "already_closed")
                # Safety: only positions we own
                ours = pos.magic == settings.order_magic or (pos.comment or "").startswith(
                    f"{settings.order_comment_prefix}:"
                )
                if not ours:
                    return _result(req, "skipped_not_ours", "position not tagged as CTP")
                tick = mt5.symbol_info_tick(pos.symbol)
                close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
                price = tick.bid if pos.type == mt5.POSITION_TYPE_BUY else tick.ask
                res = mt5.order_send({
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": pos.symbol,
                    "position": pos.ticket,
                    "volume": pos.volume,
                    "type": close_type,
                    "price": price,
                    "deviation": settings.default_deviation,
                    "magic": settings.order_magic,
                    "comment": f"{settings.order_comment_prefix}:AUDIT_FIX"[:31],
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_IOC,
                })
                if res and res.retcode in (10009, 10008):
                    return _result(req, "auto_fixed", "force_close ok",
                                   {"position": pos.ticket, "retcode": int(res.retcode)})
                return _result(req, "auto_fix_failed",
                               getattr(res, "comment", "") or "force_close failed",
                               {"retcode": int(getattr(res, "retcode", 0) or 0)})

            if req.command == "FORCE_MODIFY_SL_TP":
                if pos is None:
                    return _result(req, "not_found")
                ours = pos.magic == settings.order_magic or (pos.comment or "").startswith(
                    f"{settings.order_comment_prefix}:"
                )
                if not ours:
                    return _result(req, "skipped_not_ours")
                res = mt5.order_send({
                    "action": mt5.TRADE_ACTION_SLTP,
                    "symbol": pos.symbol,
                    "position": pos.ticket,
                    "sl": req.sl or 0.0,
                    "tp": req.tp or 0.0,
                })
                if res and res.retcode == 10009:
                    return _result(req, "auto_fixed", "sltp ok")
                return _result(req, "auto_fix_failed", getattr(res, "comment", "") or "sltp failed")

            return _result(req, "error", f"unknown command {req.command}")
    except Exception as e:  # noqa: BLE001
        log.exception("audit failed for %s", req.execution_order_id)
        return _result(req, "error", str(e))
