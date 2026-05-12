"""Central execution safety guard for V2.

Provides `can_execute_order(...)` enforcing the DEMO → REAL ramp-up.

Modes:
  * DRY_RUN        — never calls mt5.order_send. Always blocked at the
                     real-execution layer. Validation/simulation only.
  * DEMO_ONLY      — order_send permitted ONLY for accounts whose type
                     is 'demo' AND that are listed in DEMO_WHITELIST_ACCOUNTS
                     (when the whitelist is non-empty; if empty, any demo).
                     Real accounts are always blocked.
  * LIVE_WHITELIST — order_send permitted for real accounts ONLY if the
                     account_id (UUID) or login (int) is in
                     LIVE_WHITELIST_ACCOUNTS. Demo also allowed if listed
                     in DEMO_WHITELIST_ACCOUNTS.

Independent kill-switch:
  * V2_ORDER_EXECUTION_ENABLED=false  → blocks ALL real order_send
    regardless of mode/whitelist.

Returns a `GuardDecision` with allowed flag, reason, and structured fields
for logs. Never raises.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional, Set
from uuid import UUID

from ..config import get_v2_settings
from ..utils.logger import get_logger

log = get_logger("safety_guard")


VALID_MODES = {"DRY_RUN", "DEMO_ONLY", "LIVE_WHITELIST"}


@dataclass
class GuardDecision:
    allowed: bool
    execution_mode: str
    order_execution_enabled: bool
    account_allowed: bool
    reason_if_blocked: Optional[str] = None
    # Convenience
    simulate_only: bool = False  # True when DRY_RUN

    def log_fields(self) -> dict:
        return asdict(self)


def _parse_set(raw: str) -> Set[str]:
    if not raw:
        return set()
    return {p.strip() for p in raw.split(",") if p.strip()}


def _matches_whitelist(account_id: UUID, login: Optional[int], wl: Set[str]) -> bool:
    if not wl:
        return False
    if str(account_id) in wl:
        return True
    if login is not None and str(login) in wl:
        return True
    return False


def can_execute_order(
    account_id: UUID,
    login: Optional[int],
    account_type: str,
) -> GuardDecision:
    """Decide whether a real `mt5.order_send` is allowed for this account.

    Args:
        account_id: V2 account UUID.
        login:      MT5 login number (may be None if not yet known).
        account_type: 'demo' | 'real' (case-insensitive).
    """
    s = get_v2_settings()
    mode = (s.EXECUTION_MODE or "DRY_RUN").upper()
    if mode not in VALID_MODES:
        mode = "DRY_RUN"
    enabled = bool(s.ORDER_EXECUTION_ENABLED)
    atype = (account_type or "").lower()

    live_wl = _parse_set(s.LIVE_WHITELIST_ACCOUNTS)
    demo_wl = _parse_set(s.DEMO_WHITELIST_ACCOUNTS)

    base = {
        "execution_mode": mode,
        "order_execution_enabled": enabled,
    }

    # Mode 1 — DRY_RUN: never allowed, always simulate
    if mode == "DRY_RUN":
        return GuardDecision(
            allowed=False,
            account_allowed=False,
            reason_if_blocked="dry_run_mode",
            simulate_only=True,
            **base,
        )

    # Kill-switch: even in DEMO_ONLY/LIVE_WHITELIST, block if disabled
    if not enabled:
        return GuardDecision(
            allowed=False,
            account_allowed=False,
            reason_if_blocked="order_execution_disabled",
            **base,
        )

    # Mode 2 — DEMO_ONLY
    if mode == "DEMO_ONLY":
        if atype != "demo":
            return GuardDecision(
                allowed=False, account_allowed=False,
                reason_if_blocked="demo_only_mode_real_account_blocked",
                **base,
            )
        # If demo whitelist is set, account must be in it. Else allow any demo.
        if demo_wl and not _matches_whitelist(account_id, login, demo_wl):
            return GuardDecision(
                allowed=False, account_allowed=False,
                reason_if_blocked="account_not_in_demo_whitelist",
                **base,
            )
        return GuardDecision(allowed=True, account_allowed=True, **base)

    # Mode 3 — LIVE_WHITELIST
    if mode == "LIVE_WHITELIST":
        if atype == "real":
            if _matches_whitelist(account_id, login, live_wl):
                return GuardDecision(allowed=True, account_allowed=True, **base)
            return GuardDecision(
                allowed=False, account_allowed=False,
                reason_if_blocked="account_not_in_live_whitelist",
                **base,
            )
        if atype == "demo":
            # Demo still allowed if explicitly listed; otherwise blocked
            # to keep LIVE_WHITELIST strict and predictable.
            if _matches_whitelist(account_id, login, demo_wl):
                return GuardDecision(allowed=True, account_allowed=True, **base)
            return GuardDecision(
                allowed=False, account_allowed=False,
                reason_if_blocked="demo_not_in_demo_whitelist",
                **base,
            )
        return GuardDecision(
            allowed=False, account_allowed=False,
            reason_if_blocked=f"unknown_account_type:{atype!r}",
            **base,
        )

    # Defensive default
    return GuardDecision(
        allowed=False, account_allowed=False,
        reason_if_blocked="unknown_mode",
        **base,
    )
