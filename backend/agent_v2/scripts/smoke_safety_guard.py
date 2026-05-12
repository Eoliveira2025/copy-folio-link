"""Smoke test for the V2 execution safety guard.

Runs `can_execute_order` across the three modes and prints the decisions.
No DB, no MT5, no network. Safe to run anywhere.

Usage:
    python -m agent_v2.scripts.smoke_safety_guard
"""

from __future__ import annotations

import os
from uuid import uuid4

# Override env BEFORE importing settings (lru_cache)
os.environ.setdefault("V2_EXECUTION_MODE", "DRY_RUN")
os.environ.setdefault("V2_ORDER_EXECUTION_ENABLED", "false")

from agent_v2.config import get_v2_settings  # noqa: E402
from agent_v2.exec.safety_guard import can_execute_order  # noqa: E402


def _reset(mode: str, enabled: bool, live_wl: str = "", demo_wl: str = "") -> None:
    os.environ["V2_EXECUTION_MODE"] = mode
    os.environ["V2_ORDER_EXECUTION_ENABLED"] = "true" if enabled else "false"
    os.environ["V2_LIVE_WHITELIST_ACCOUNTS"] = live_wl
    os.environ["V2_DEMO_WHITELIST_ACCOUNTS"] = demo_wl
    get_v2_settings.cache_clear()


def _show(label: str, dec) -> None:
    print(f"[{label}] allowed={dec.allowed} simulate_only={dec.simulate_only} "
          f"reason={dec.reason_if_blocked} fields={dec.log_fields()}")


def main() -> int:
    demo_id = uuid4()
    real_id = uuid4()
    real_login = 12345678

    print("── DRY_RUN ──")
    _reset("DRY_RUN", False)
    _show("dry/demo", can_execute_order(demo_id, 111, "demo"))
    _show("dry/real", can_execute_order(real_id, real_login, "real"))

    print("\n── DEMO_ONLY (enabled, empty demo_wl) ──")
    _reset("DEMO_ONLY", True)
    _show("demo_any", can_execute_order(demo_id, 111, "demo"))
    _show("real_blocked", can_execute_order(real_id, real_login, "real"))

    print("\n── DEMO_ONLY (kill-switch off) ──")
    _reset("DEMO_ONLY", False)
    _show("disabled", can_execute_order(demo_id, 111, "demo"))

    print("\n── DEMO_ONLY (demo_wl filter) ──")
    _reset("DEMO_ONLY", True, demo_wl=f"{demo_id}")
    _show("demo_in_wl", can_execute_order(demo_id, 111, "demo"))
    _show("demo_not_in_wl", can_execute_order(uuid4(), 222, "demo"))

    print("\n── LIVE_WHITELIST ──")
    _reset("LIVE_WHITELIST", True, live_wl=f"{real_id},99999999")
    _show("real_in_wl_uuid", can_execute_order(real_id, real_login, "real"))
    _show("real_in_wl_login", can_execute_order(uuid4(), 99999999, "real"))
    _show("real_not_in_wl", can_execute_order(uuid4(), 1, "real"))
    _show("demo_blocked_default", can_execute_order(demo_id, 111, "demo"))

    print("\n── LIVE_WHITELIST (kill-switch off) ──")
    _reset("LIVE_WHITELIST", False, live_wl=f"{real_id}")
    _show("disabled_real", can_execute_order(real_id, real_login, "real"))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
