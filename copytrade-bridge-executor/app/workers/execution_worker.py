"""Consume bridge:execute:* queues from Redis."""
from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Iterable

from pydantic import ValidationError

from app.config import settings
from app.redis_client import get_redis
from app.schemas.execution import ExecutionOrder
from app.services import execution_service, result_reporter
from app.utils.logger import get_logger

log = get_logger("worker.exec")

# Internal counters for /status
metrics = {
    "received": 0,
    "executed": 0,
    "simulated": 0,
    "failed": 0,
    "skipped": 0,
    "queues_seen": 0,
}
_metrics_lock = threading.Lock()


def _bump(field: str) -> None:
    with _metrics_lock:
        metrics[field] = metrics.get(field, 0) + 1


def _discover_queues(r) -> list[str]:
    if settings.test_queue:
        return [settings.test_queue]
    pattern = f"{settings.queue_prefix}:*"
    return [k for k in r.scan_iter(match=pattern, _type="list", count=200)]


def _handle_payload(raw: str) -> None:
    _bump("received")
    try:
        data = json.loads(raw)
        order = ExecutionOrder(**data)
    except (ValueError, ValidationError) as e:
        log.error("invalid payload: %s", e)
        _bump("failed")
        return

    result = execution_service.execute(order)
    _bump(result.status)
    try:
        result_reporter.publish_execution(result)
    except Exception:  # noqa: BLE001
        log.exception("failed to publish result")


def run(stop_event: threading.Event) -> None:
    log.info("execution worker starting (mode=%s, real=%s, max_workers=%d)",
             settings.executor_mode, settings.enable_real_trading, settings.max_workers)
    r = get_redis()
    pool = ThreadPoolExecutor(max_workers=settings.max_workers, thread_name_prefix="exec")

    last_scan = 0.0
    queues: list[str] = []

    try:
        while not stop_event.is_set():
            now = time.time()
            if now - last_scan >= settings.queue_scan_interval_seconds or not queues:
                queues = _discover_queues(r)
                metrics["queues_seen"] = len(queues)
                last_scan = now
                if not queues:
                    time.sleep(settings.queue_scan_interval_seconds)
                    continue

            try:
                got = r.blpop(queues, timeout=settings.blpop_timeout_seconds)
            except Exception:
                log.exception("redis blpop error")
                time.sleep(1.0)
                continue
            if not got:
                continue
            _, raw = got
            pool.submit(_handle_payload, raw)
    finally:
        pool.shutdown(wait=True, cancel_futures=False)
        log.info("execution worker stopped")
