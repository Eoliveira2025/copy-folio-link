"""Entrypoint: starts execution worker, audit worker and optional health API."""
from __future__ import annotations

import signal
import threading
import time

from app.config import settings
from app.mt5 import terminal_manager
from app.utils.logger import configure_logging, get_logger
from app.workers import audit_worker, execution_worker

log = get_logger("main")


def main() -> None:
    configure_logging()
    log.info(
        "starting CopyTrade Pro Bridge Executor id=%s mode=%s real=%s",
        settings.executor_id, settings.executor_mode, settings.enable_real_trading,
    )

    stop_event = threading.Event()

    def _stop(signum, _frame):  # noqa: ARG001
        log.info("signal %s received, shutting down", signum)
        stop_event.set()

    signal.signal(signal.SIGINT, _stop)
    try:
        signal.signal(signal.SIGTERM, _stop)
    except (AttributeError, ValueError):
        pass

    if settings.enable_real_trading:
        terminal_manager.initialize()

    threads: list[threading.Thread] = []

    t_exec = threading.Thread(target=execution_worker.run, args=(stop_event,),
                              name="exec-worker", daemon=False)
    t_exec.start()
    threads.append(t_exec)

    if settings.enable_auditor:
        t_audit = threading.Thread(target=audit_worker.run, args=(stop_event,),
                                   name="audit-worker", daemon=False)
        t_audit.start()
        threads.append(t_audit)

    if settings.health_api_enabled:
        from app import health_api
        health_api.serve_in_thread(stop_event)

    try:
        while not stop_event.is_set():
            time.sleep(0.5)
    finally:
        deadline = time.time() + settings.shutdown_timeout_seconds
        for t in threads:
            remaining = max(0.1, deadline - time.time())
            t.join(timeout=remaining)
        terminal_manager.shutdown()
        log.info("shutdown complete")


if __name__ == "__main__":
    main()
