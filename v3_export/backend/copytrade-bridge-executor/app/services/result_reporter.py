"""Publish execution / audit results back to Redis."""
from __future__ import annotations

import json

from app.config import settings
from app.redis_client import get_redis
from app.schemas.audit import AuditResult
from app.schemas.execution import ExecutionResult
from app.utils.logger import get_logger

log = get_logger("reporter")


def publish_execution(result: ExecutionResult) -> None:
    payload = result.model_dump_json()
    get_redis().rpush(settings.result_queue, payload)
    log.info("published result %s status=%s", result.execution_order_id, result.status)


def publish_audit(result: AuditResult) -> None:
    get_redis().rpush(settings.audit_queue, result.model_dump_json())
    log.info("published audit %s status=%s", result.execution_order_id, result.status)
