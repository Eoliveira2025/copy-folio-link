"""V2 agent entry point.

Boots:
  * TerminalAllocator
  * PoolWorkerRegistry (lazy: workers built per pool as accounts arrive)
  * MasterMonitor per V2-flagged master
  * Distributor V2 (Redis subscriber)
  * HealthMonitor

Defaults are SAFE:
  V2_EXECUTION_MODE=DRY_RUN
  V2_ORDER_EXECUTION_ENABLED=false
  V2_SESSION_DRY_RUN=true
  V2_CLOSE_RECONCILER_ENABLED=false

Run:
  python -m agent_v2.main

This module deliberately avoids loading masters/clients from DB by
itself — that wiring lives in a future bootstrapper. For now the entry
point starts the long-running services and idles, which is enough for
DRY_RUN end-to-end.
"""

from __future__ import annotations

import signal
import time

from .config import get_v2_settings
from .health.heartbeat import HealthMonitor
from .pool.allocator import TerminalAllocator
from .pool.auto_provisioner import strategy_key_for
from .utils.logger import get_logger
from .wiring import PoolWorkerRegistry


def _strategy_key_resolver(strategy_id):
    # Without DB lookup, default to a generic key. Real resolver injected
    # by the bootstrapper in production.
    return "default"


def main() -> int:
    log = get_logger("main")
    s = get_v2_settings()
    log.info(
        "V2 agent starting",
        extra={
            "action": "v2_boot",
            "execution_mode": s.EXECUTION_MODE,
            "order_execution_enabled": s.ORDER_EXECUTION_ENABLED,
            "redis_url": s.REDIS_URL,
            "redis_prefix": s.REDIS_PREFIX,
        },
    )

    allocator = TerminalAllocator(strategy_key_resolver=_strategy_key_resolver)
    registry = PoolWorkerRegistry()
    health = HealthMonitor(registry=registry)
    health.start()

    stop = {"flag": False}

    def _handler(signum, frame):
        log.info("shutdown signal received",
                 extra={"action": "shutdown_signal", "signum": signum})
        stop["flag"] = True

    signal.signal(signal.SIGINT, _handler)
    signal.signal(signal.SIGTERM, _handler)

    while not stop["flag"]:
        time.sleep(1.0)

    health.stop()
    registry.stop_all()
    log.info("V2 agent stopped", extra={"action": "v2_stop"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
