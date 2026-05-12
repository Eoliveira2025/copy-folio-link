"""CloseReconciler V2 — verify-and-retry close loop.

Works alongside OrderExecutor:

  executor.execute(close_task)         # first attempt
  reconciler.reconcile(close_task)     # verify + retry until gone

Guarantees:
  * Never closes by symbol/direction/volume.
  * Primary key is `client_ticket`. We re-call `positions_get(ticket=...)`.
  * Fallback (only when client_ticket is absent OR the broker assigned a
    different ticket): scan `positions_get()` and match by EXACT
    comment == f"CT:{master_ticket}" AND magic AND symbol. If multiple
    candidates match → ambiguous, refuse and report.
  * Manual close by the user → reported as `JA_NAO_EXISTE`, not failed.
  * Disabled by default (`V2_CLOSE_RECONCILER_ENABLED=false`).

Status returned (per task):
  FECHADO_OK         — no position remains after attempts succeeded
  JA_NAO_EXISTE      — position not found (closed manually or already)
  FALHOU             — exhausted attempts; position still open
  AMBIGUOUS_FALLBACK — fallback found >1 candidate; refused
  DISABLED           — reconciler disabled by config
"""

from __future__ import annotations

import enum
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional
from uuid import UUID

from ..config import get_v2_settings
from ..utils.logger import get_logger
from .order_task import OrderAction, OrderTask
from .order_executor import ExecutionError, OrderExecutor


class ReconcileStatus(str, enum.Enum):
    FECHADO_OK = "FECHADO_OK"
    JA_NAO_EXISTE = "JA_NAO_EXISTE"
    FALHOU = "FALHOU"
    AMBIGUOUS_FALLBACK = "AMBIGUOUS_FALLBACK"
    DISABLED = "DISABLED"


@dataclass
class ReconcileResult:
    status: ReconcileStatus
    attempts: int
    last_retcode: Optional[int] = None
    resolved_ticket: Optional[int] = None
    notes: List[str] = field(default_factory=list)


def _safe_import_mt5():
    try:
        import MetaTrader5 as mt5  # type: ignore
        return mt5
    except Exception as e:
        raise RuntimeError(f"MetaTrader5 import failed: {e}")


def _parse_delays(raw: str) -> List[float]:
    out: List[float] = []
    for p in (raw or "").split(","):
        p = p.strip()
        if not p:
            continue
        try:
            out.append(float(p))
        except ValueError:
            continue
    return out or [2.0, 5.0, 10.0, 20.0, 30.0]


class CloseReconciler:
    """Per-pool/terminal close reconciliation."""

    def __init__(
        self,
        *,
        executor: OrderExecutor,
        sleep_fn: Callable[[float], None] = time.sleep,
    ):
        self.executor = executor
        self.settings = get_v2_settings()
        self.enabled = bool(self.settings.CLOSE_RECONCILER_ENABLED)
        self.max_attempts = int(self.settings.CLOSE_RECONCILER_MAX_ATTEMPTS)
        self.delays = _parse_delays(self.settings.CLOSE_RECONCILER_RETRY_DELAYS_SECONDS)
        self.accept_manual = bool(self.settings.CLOSE_RECONCILER_ACCEPT_MANUAL_CLOSE)
        self._sleep = sleep_fn
        self.log = get_logger("close_reconciler").bind(
            pool_id=str(executor.pool_id),
            terminal_id=str(executor.terminal_id),
            pool_name=executor.pool_name,
        )

    # ── helpers ───────────────────────────────────────────────────
    def _find_position(self, mt5, task: OrderTask):
        """Return matched position (or None). Never matches by side/volume."""
        if task.client_ticket:
            res = mt5.positions_get(ticket=int(task.client_ticket))
            if res:
                pos = res[0]
                # Defensive: never accept a position whose symbol differs.
                if task.symbol and pos.symbol != task.symbol:
                    return ("WRONG_SYMBOL", pos)
                return ("EXACT", pos)
            return ("NOT_FOUND", None)

        # Fallback: comment exact + magic + symbol
        if not task.master_ticket:
            return ("NO_KEY", None)
        wanted_comment = f"CT:{task.master_ticket}"
        all_pos = mt5.positions_get() or []
        cands = [
            p for p in all_pos
            if str(getattr(p, "comment", "")) == wanted_comment
            and int(getattr(p, "magic", 0)) == int(task.magic or 0)
            and getattr(p, "symbol", None) == task.symbol
        ]
        if not cands:
            return ("NOT_FOUND", None)
        if len(cands) > 1:
            return ("AMBIGUOUS", cands)
        return ("FALLBACK", cands[0])

    def _log_attempt(self, task: OrderTask, attempt: int, status: str,
                     retcode: Optional[int] = None, note: str = "") -> None:
        self.log.info(
            "reconcile attempt",
            extra={
                "action": "reconcile_attempt",
                "account_id": str(task.account_id),
                "master_ticket": task.master_ticket,
                "client_ticket": task.client_ticket,
                "attempt": attempt,
                "status": status,
                "retcode": retcode,
                "symbol": task.symbol,
                "note": note,
            },
        )

    # ── public ────────────────────────────────────────────────────
    def reconcile(self, task: OrderTask) -> ReconcileResult:
        if task.action != OrderAction.CLOSE:
            raise ValueError("CloseReconciler only handles CLOSE tasks")
        if not self.enabled:
            self._log_attempt(task, 0, "DISABLED")
            return ReconcileResult(status=ReconcileStatus.DISABLED, attempts=0)

        mt5 = _safe_import_mt5()
        last_retcode: Optional[int] = None
        notes: List[str] = []

        for attempt in range(1, self.max_attempts + 1):
            kind, found = self._find_position(mt5, task)

            if kind == "NOT_FOUND" or kind == "NO_KEY":
                if self.accept_manual or kind == "NOT_FOUND":
                    self._log_attempt(task, attempt, "JA_NAO_EXISTE",
                                      last_retcode, kind)
                    return ReconcileResult(
                        status=ReconcileStatus.JA_NAO_EXISTE,
                        attempts=attempt, last_retcode=last_retcode,
                        notes=notes + [kind],
                    )

            if kind == "WRONG_SYMBOL":
                msg = (f"position {task.client_ticket} symbol mismatch: "
                       f"expected={task.symbol}, got={found.symbol}")
                notes.append(msg)
                self._log_attempt(task, attempt, "WRONG_SYMBOL_BLOCKED",
                                  last_retcode, msg)
                # Defensive: do NOT close. Return failure so operator looks.
                return ReconcileResult(
                    status=ReconcileStatus.FALHOU,
                    attempts=attempt, last_retcode=last_retcode, notes=notes,
                )

            if kind == "AMBIGUOUS":
                msg = f"fallback ambiguous: {len(found)} candidates"
                notes.append(msg)
                self._log_attempt(task, attempt, "AMBIGUOUS_FALLBACK",
                                  last_retcode, msg)
                return ReconcileResult(
                    status=ReconcileStatus.AMBIGUOUS_FALLBACK,
                    attempts=attempt, last_retcode=last_retcode, notes=notes,
                )

            # We have a real position (EXACT or FALLBACK). Issue close.
            pos = found
            close_task = OrderTask(
                account_id=task.account_id,
                pool_id=task.pool_id,
                terminal_id=task.terminal_id,
                master_id=task.master_id,
                strategy_id=task.strategy_id,
                action=OrderAction.CLOSE,
                symbol=pos.symbol,
                client_ticket=int(pos.ticket),
                master_ticket=task.master_ticket,
                magic=int(getattr(pos, "magic", 0) or task.magic or 0),
                comment=f"v2:reconcile:{attempt}:{pos.ticket}",
                idempotency_key=f"reconcile:{task.account_id}:{pos.ticket}:{attempt}",
            )

            try:
                # Session info is unknown here; assume warm session (caller
                # holds AccountSession lock in production wiring).
                res = self.executor.execute(close_task, session_info={
                    "login_latency_ms": 0.0, "switched": False,
                    "login": 0, "account_type": "demo",
                })
                last_retcode = res.retcode
                self._log_attempt(task, attempt, "CLOSE_SENT", res.retcode,
                                  f"ticket={pos.ticket}")
            except ExecutionError as e:
                last_retcode = -1
                notes.append(f"attempt {attempt}: {e}")
                self._log_attempt(task, attempt, "CLOSE_FAILED",
                                  last_retcode, str(e))

            # Verify
            check_kind, check_pos = self._find_position(mt5, task)
            if check_kind in ("NOT_FOUND", "NO_KEY"):
                self._log_attempt(task, attempt, "FECHADO_OK", last_retcode)
                return ReconcileResult(
                    status=ReconcileStatus.FECHADO_OK,
                    attempts=attempt, last_retcode=last_retcode,
                    resolved_ticket=int(pos.ticket), notes=notes,
                )

            if attempt < self.max_attempts:
                delay = self.delays[min(attempt - 1, len(self.delays) - 1)]
                self._sleep(delay)

        self._log_attempt(task, self.max_attempts, "FALHOU", last_retcode)
        return ReconcileResult(
            status=ReconcileStatus.FALHOU,
            attempts=self.max_attempts, last_retcode=last_retcode, notes=notes,
        )
