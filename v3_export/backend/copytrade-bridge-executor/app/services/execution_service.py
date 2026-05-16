"""Execute one ExecutionOrder against MT5 (or simulate)."""
from __future__ import annotations

from datetime import datetime, timezone

from app.config import settings
from app.mt5 import account_session, order_executor, symbol_resolver, terminal_manager
from app.schemas.execution import ExecutionOrder, ExecutionResult
from app.utils.logger import get_logger

log = get_logger("svc.exec")
orders_log = get_logger("orders")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def execute(order: ExecutionOrder) -> ExecutionResult:
    orders_log.info(
        "received order",
        extra={"order": order.model_dump()},
    )

    base = dict(
        execution_order_id=order.execution_order_id,
        executor_id=settings.executor_id,
        client_login=order.client_login,
        action=order.action,
        symbol=order.symbol,
        lot=order.lot,
        executed_at=_now(),
    )

    # Simulation mode
    if not settings.enable_real_trading:
        msg = "simulated (ENABLE_REAL_TRADING=false)"
        log.info("[SIM] %s %s %s lot=%s", order.action, order.symbol, order.client_login, order.lot)
        return ExecutionResult(status="simulated", message=msg, **base)

    if not terminal_manager.is_available():
        return ExecutionResult(status="failed", error="mt5_unavailable", message="MetaTrader5 package missing", **base)

    try:
        with account_session.login_account(
            order.client_login, order.client_server, order.client_password
        ) as mt5:
            symbol = symbol_resolver.resolve(order.symbol)
            if not symbol:
                return ExecutionResult(status="failed", error="symbol_not_found",
                                       message=f"symbol {order.symbol} not available", **base)

            if order.action == "OPEN":
                lot = symbol_resolver.normalize_lot(symbol, order.lot)
                if lot is None:
                    return ExecutionResult(status="failed", error="lot_invalid",
                                           message="cannot normalize lot", **base)
                base["lot"] = lot
                res = order_executor.execute_open(mt5, order, symbol, lot)
            elif order.action == "CLOSE":
                res = order_executor.execute_close(mt5, order)
            elif order.action in ("MODIFY", "SLTP"):
                res = order_executor.execute_modify(mt5, order)
            else:
                return ExecutionResult(status="failed", error="unknown_action",
                                       message=order.action, **base)

        status = "executed" if res.get("ok") else (
            "skipped" if res.get("message") in {"already_closed_or_not_found", "skipped_not_ours"} else "failed"
        )
        return ExecutionResult(
            status=status,
            retcode=res.get("retcode"),
            mt5_order=res.get("mt5_order"),
            mt5_position=res.get("mt5_position"),
            message=res.get("message", ""),
            error=None if status in ("executed", "skipped") else res.get("message"),
            **base,
        )
    except Exception as e:  # noqa: BLE001
        log.exception("execution failed for %s", order.execution_order_id)
        return ExecutionResult(status="failed", error=type(e).__name__, message=str(e), **base)
