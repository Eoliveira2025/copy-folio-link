"""Engine configuration."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class EngineSettings(BaseSettings):
    REDIS_URL: str = "redis://localhost:6379/0"
    DATABASE_URL_SYNC: str = "postgresql://postgres:postgres@localhost:5432/copytrade"
    MT5_CREDENTIAL_KEY: str = "change-me-32-byte-base64-key===="

    # Polling
    MASTER_POLL_INTERVAL_MS: int = 100  # 100ms for near-real-time
    HEALTH_CHECK_INTERVAL_S: int = 30

    # Execution
    MAX_RETRY_ATTEMPTS: int = 3
    RETRY_DELAY_MS: int = 500
    EXECUTION_TIMEOUT_S: int = 10

    # Workers
    WORKER_COUNT: int = 4  # per-master worker pool size

    # Lot calculation
    MIN_LOT: float = 0.01
    MAX_LOT: float = 100.0
    LOT_STEP: float = 0.01

    class Config:
        env_file = ".env"


@lru_cache()
def get_engine_settings() -> EngineSettings:
    return EngineSettings()
