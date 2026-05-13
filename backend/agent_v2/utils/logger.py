"""Structured logger for V2.

All log records carry contextual fields:
  master_id, strategy_id, pool_id, pool_name, terminal_id, account_id,
  action, order_id, retcode, latency_ms.

Output: JSON one-line per record, written to:
  - stdout (captured by Windows service)
  - C:\\copytrade_v2_logs\\<strategy>\\<pool>\\agent.log (if path set)
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from ..config import get_v2_settings

_CTX_FIELDS = (
    "master_id",
    "strategy_id",
    "pool_id",
    "pool_name",
    "terminal_id",
    "account_id",
    "action",
    "order_id",
    "client_ticket",
    "master_ticket",
    "retcode",
    "latency_ms",
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key in _CTX_FIELDS:
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        
        # Inject context from extra if present but not in record attributes
        if hasattr(record, "extra") and isinstance(record.extra, dict):
            for k, v in record.extra.items():
                if k not in payload:
                    payload[k] = v

        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


class SupportFormatter(logging.Formatter):
    """Human-readable formatter for support and console."""
    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ctx_list = []
        for key in _CTX_FIELDS:
            val = getattr(record, key, None)
            if val is not None:
                ctx_list.append(f"{key}={val}")
        
        # Also check extra
        if hasattr(record, "extra") and isinstance(record.extra, dict):
            for k, v in record.extra.items():
                if k not in _CTX_FIELDS:
                    ctx_list.append(f"{k}={v}")

        ctx_str = f" [{', '.join(ctx_list)}]" if ctx_list else ""
        return f"[{ts}] {record.levelname:7} | {record.name:15} | {record.getMessage()}{ctx_str}"



class ContextLogger(logging.LoggerAdapter):
    """Logger adapter that injects contextual fields via `extra=`."""

    def process(self, msg, kwargs):
        extra = kwargs.setdefault("extra", {})
        for k, v in self.extra.items():
            extra.setdefault(k, v)
        return msg, kwargs

    def bind(self, **fields: Any) -> "ContextLogger":
        merged = {**self.extra, **fields}
        return ContextLogger(self.logger, merged)


_configured = False


def _configure_root() -> None:
    global _configured
    if _configured:
        return
    settings = get_v2_settings()
    root = logging.getLogger("agent_v2")
    root.setLevel(logging.INFO)
    root.handlers.clear()

    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(JsonFormatter())
    root.addHandler(stream)

    try:
        log_dir = Path(settings.V2_LOGS_DIR)
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_dir / "agent_v2.log",
            maxBytes=50 * 1024 * 1024,
            backupCount=10,
            encoding="utf-8",
        )
        file_handler.setFormatter(JsonFormatter())
        root.addHandler(file_handler)
    except OSError:
        # Non-Windows / dev env — stdout only is fine.
        pass

    root.propagate = False
    _configured = True


def get_logger(name: str, **context: Any) -> ContextLogger:
    """Return a ContextLogger under the `agent_v2.<name>` namespace.

    Example:
        log = get_logger("pool", strategy_id=..., pool_name="pool_low_01")
        log.info("pool started")
    """
    _configure_root()
    base = logging.getLogger(f"agent_v2.{name}")
    return ContextLogger(base, dict(context))


__all__ = ["get_logger", "ContextLogger", "JsonFormatter"]
