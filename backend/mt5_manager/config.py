"""MT5 Terminal Manager configuration."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class ManagerSettings(BaseSettings):
    REDIS_URL: str = "redis://localhost:6379/0"
    DATABASE_URL_SYNC: str = "postgresql://postgres:postgres@localhost:5432/copytrade"
    MT5_CREDENTIAL_KEY: str = "change-me-32-byte-base64-key===="

    # Terminal paths (Windows VPS)
    MT5_TERMINAL_PATH: str = "C:\\Program Files\\MetaTrader 5\\terminal64.exe"
    MT5_DATA_DIR_BASE: str = "C:\\MT5Terminals"  # Each account gets a subfolder

    # Pool settings
    MAX_TERMINALS: int = 500  # Max concurrent MT5 processes
    SPAWN_COOLDOWN_S: float = 2.0  # Delay between spawns to avoid overwhelming the system
    PROCESS_STARTUP_TIMEOUT_S: int = 30

    # Watchdog
    WATCHDOG_INTERVAL_S: int = 15
    HEARTBEAT_STALE_S: int = 45  # Consider dead after this many seconds
    MAX_RECONNECT_ATTEMPTS: int = 5
    RECONNECT_BACKOFF_BASE_S: float = 5.0  # Exponential backoff

    # Auto-provisioning
    PROVISION_POLL_INTERVAL_S: int = 10  # Check for new accounts

    # Health reporting
    HEALTH_REPORT_INTERVAL_S: int = 30

    # Resource limits
    MAX_MEMORY_PER_TERMINAL_MB: int = 256
    CPU_AFFINITY_ENABLED: bool = False

    class Config:
        env_file = ".env"


@lru_cache()
def get_manager_settings() -> ManagerSettings:
    return ManagerSettings()
