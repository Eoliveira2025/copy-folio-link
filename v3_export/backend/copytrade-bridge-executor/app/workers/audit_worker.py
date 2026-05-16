"""Consume bridge:audit:check:* and bridge:audit:fix:* queues."""
from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from pydantic import ValidationError

from app.config import settings
from app.redis_client import get_redis
from app.schemas.audit import AuditRequest
from app.services import audit_service, result_reporter
from app.utils.logger import get_logger

log = get_logger("worker.audit")

audit_metrics = {"received": 0, "matched": 0, "fixed": 0, "failed": 0}
_lock = threading.Lock()


def _bump(field: str) -> None:
    with _lock:
        audit_metrics[field] = audit_metrics.get(field, 0) + 1


def _discover(r) -> list[str]:
    keys: list[str] = []
    for prefix in (settings.audit_check_prefix, settings.audit_fix_prefix):
        keys.extend(r.scan_iter(match=f"{prefix}:*", _type="list", count=200))
    return keys


def _handle(raw: str) -> None:
    _bump("received")
    try:
        data = json.loads(raw)
        req = AuditRequest(**data)
    except (ValueError, ValidationError) as e:
        log.error("invalid audit payload: %s", e)
        _bump("failed")
        return
    res = audit_service.run(req)
    if res.status == "matched":
        _bump("matched")
    elif res.status == "auto_fixed":
        _bump("fixed")
    elif res.status in ("error", "auto_fix_failed"):
        _bump("failed")
    try:
        result_reporter.publish_audit(res)
    except Exception:  # noqa: BLE001
        log.exception("failed to publish audit result")


def run(stop_event: threading.Event) -> None:
    if not settings.enable_auditor:
        log.info("auditor disabled (ENABLE_AUDITOR=false)")
        return
    log.info("audit worker starting")
    r = get_redis()
    pool = ThreadPoolExecutor(max_workers=max(2, settings.max_workers // 2),
                              thread_name_prefix="audit")
    queues: list[str] = []
    last_scan = 0.0
    try:
        while not stop_event.is_set():
            now = time.time()
            if now - last_scan >= settings.queue_scan_interval_seconds or not queues:
                queues = _discover(r)
                last_scan = now
                if not queues:
                    time.sleep(settings.queue_scan_interval_seconds)
                    continue
            try:
                got = r.blpop(queues, timeout=settings.blpop_timeout_seconds)
            except Exception:
                log.exception("redis blpop error (audit)")
                time.sleep(1.0)
                continue
            if not got:
                continue
            _, raw = got
            pool.submit(_handle, raw)
    finally:
        pool.shutdown(wait=True)
        log.info("audit worker stopped")
