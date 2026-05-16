"""Structured logging setup."""
from __future__ import annotations

import logging
import logging.handlers
import os
from pathlib import Path

from pythonjsonlogger import jsonlogger

from app.config import settings

_configured = False


def _make_handler(path: Path, level: int) -> logging.Handler:
    path.parent.mkdir(parents=True, exist_ok=True)
    h = logging.handlers.RotatingFileHandler(
        path, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    h.setLevel(level)
    h.setFormatter(
        jsonlogger.JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s",
            rename_fields={"asctime": "ts", "levelname": "level"},
        )
    )
    return h


def configure_logging() -> None:
    global _configured
    if _configured:
        return

    log_dir = Path(settings.log_dir)
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    root = logging.getLogger()
    root.setLevel(level)
    # Console
    console = logging.StreamHandler()
    console.setLevel(level)
    console.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    root.addHandler(console)
    # Files
    root.addHandler(_make_handler(log_dir / "executor.log", level))
    err = _make_handler(log_dir / "errors.log", logging.ERROR)
    root.addHandler(err)

    orders = logging.getLogger("orders")
    orders.propagate = False
    orders.setLevel(level)
    orders.addHandler(_make_handler(log_dir / "orders.log", level))

    _configured = True


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name)
