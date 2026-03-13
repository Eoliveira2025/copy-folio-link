"""
Structured logging configuration for all CopyTrade Pro services.

Usage:
    from app.core.logging_config import setup_logging
    setup_logging("api")  # or "engine", "mt5-manager", "celery"
"""

import logging
import logging.handlers
import json
import os
import sys
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """Outputs log records as JSON for Loki/Promtail ingestion."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)

        if hasattr(record, "extra_data"):
            log_entry["data"] = record.extra_data

        return json.dumps(log_entry)


def setup_logging(service_name: str, log_level: str = "INFO"):
    """Configure structured logging for a service."""
    log_dir = os.environ.get("LOG_DIR", "/app/logs")
    os.makedirs(log_dir, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Clear existing handlers
    root.handlers.clear()

    json_formatter = JSONFormatter()

    # Console handler (human-readable for development)
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(
        f"%(asctime)s [{service_name}] %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    root.addHandler(console)

    # File handler (JSON for Loki)
    file_handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, f"{service_name}.log"),
        maxBytes=50 * 1024 * 1024,  # 50MB
        backupCount=5,
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(json_formatter)
    root.addHandler(file_handler)

    # Error file handler
    error_handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, f"{service_name}.error.log"),
        maxBytes=20 * 1024 * 1024,  # 20MB
        backupCount=3,
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(json_formatter)
    root.addHandler(error_handler)

    # Suppress noisy libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    logging.getLogger(service_name).info(f"Logging initialized for {service_name}")
