"""Settings for the Bridge Executor."""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Executor identity
    executor_id: str = "windows-vps-01"
    executor_mode: str = "test"  # "test" | "prod"

    # MT5
    mt5_terminal_path: str = r"C:\Program Files\MetaTrader 5\terminal64.exe"

    # Queues
    queue_prefix: str = "bridge:execute"
    result_queue: str = "bridge:results"
    audit_check_prefix: str = "bridge:audit:check"
    audit_fix_prefix: str = "bridge:audit:fix"
    audit_queue: str = "bridge:audit:results"
    test_queue: str = ""

    # Workers
    max_workers: int = 5
    shutdown_timeout_seconds: int = 15
    queue_scan_interval_seconds: float = 2.0
    blpop_timeout_seconds: int = 2

    # Orders
    order_magic: int = 777001
    order_comment_prefix: str = "CTP"
    default_deviation: int = 20

    # Safety flags
    enable_real_trading: bool = False
    enable_auditor: bool = True

    # Health API
    health_api_enabled: bool = True
    health_api_host: str = "127.0.0.1"
    health_api_port: int = 8765

    # Logs
    log_level: str = "INFO"
    log_dir: str = "logs"


settings = Settings()
