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

    # Pool settings — multi-account terminal architecture
    MAX_TERMINALS: int = 50   # Max concurrent MT5 terminal processes
    MAX_ACCOUNTS_PER_TERMINAL: int = 50  # Accounts per terminal process
    SPAWN_COOLDOWN_S: float = 2.0
    PROCESS_STARTUP_TIMEOUT_S: int = 30

    # Watchdog
    WATCHDOG_INTERVAL_S: int = 15
    HEARTBEAT_STALE_S: int = 45
    MAX_RECONNECT_ATTEMPTS: int = 5
    RECONNECT_BACKOFF_BASE_S: float = 5.0

    # Auto-provisioning
    PROVISION_POLL_INTERVAL_S: int = 10

    # Health reporting
    HEALTH_REPORT_INTERVAL_S: int = 30

    # Resource limits
    MAX_MEMORY_PER_TERMINAL_MB: int = 512
    CPU_AFFINITY_ENABLED: bool = False

    # Session management
    SESSION_HEARTBEAT_INTERVAL_S: int = 10
    SESSION_STALE_TIMEOUT_S: int = 60
    BALANCE_SYNC_INTERVAL_S: int = 30

    # Rebalancing
    REBALANCE_INTERVAL_S: int = 300  # Every 5 minutes
    REBALANCE_THRESHOLD: float = 0.2  # Trigger when imbalance > 20%

    # Strategy levels and master account mapping
    STRATEGY_LEVELS: list = [
        "low", "medium", "high", "pro", "expert", "expert_pro"
    ]

    class Config:
        env_file = ".env"


@lru_cache()
def get_manager_settings() -> ManagerSettings:
    return ManagerSettings()
