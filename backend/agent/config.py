"""Windows VPS Agent configuration."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class AgentSettings(BaseSettings):
    # ── Remote infrastructure (Ubuntu server) ─────────────────────
    DATABASE_URL_SYNC: str = "postgresql://postgres:postgres@91.98.20.163:5432/copytrade"
    REDIS_URL: str = "redis://91.98.20.163:6379/0"

    # ── Credentials encryption ────────────────────────────────────
    MT5_CREDENTIAL_KEY: str = "change-me-32-byte-base64-key===="

    # ── MT5 Terminal (Windows native) ─────────────────────────────
    MT5_TERMINAL_PATH: str = r"C:\Program Files\MetaTrader 5\terminal64.exe"

    # ── Multi-instance management ─────────────────────────────────
    MT5_BASE_PATH: str = r"C:\Program Files\MetaTrader 5"
    MT5_INSTANCES_DIR: str = r"C:\MT5_Instances"
    MT5_INSTANCE_MAPPING_FILE: str = r"C:\MT5_Instances\instances.json"
    MT5_INIT_TIMEOUT_MS: int = 60000

    # ── Master Listener ───────────────────────────────────────────
    MASTER_POLL_INTERVAL_MS: int = 50      # 50ms polling (20 polls/sec)
    ORDER_HISTORY_POLL_INTERVAL_MS: int = 100

    # ── Execution ─────────────────────────────────────────────────
    MAX_RETRY_ATTEMPTS: int = 3
    RETRY_BASE_DELAY_MS: int = 100
    MAX_SLIPPAGE_POINTS: int = 30
    SLIPPAGE_REJECT_ENABLED: bool = True

    # ── Lot calculation ───────────────────────────────────────────
    MIN_LOT: float = 0.01
    MAX_LOT: float = 100.0
    LOT_STEP: float = 0.01

    # ── Workers ───────────────────────────────────────────────────
    DISTRIBUTOR_THREAD_POOL_SIZE: int = 16

    # ── DB Sync ───────────────────────────────────────────────────
    DB_SYNC_INTERVAL_S: int = 30   # Refresh accounts/strategies every 30s
    BALANCE_SYNC_INTERVAL_S: int = 60

    # ── Health / Metrics ──────────────────────────────────────────
    HEALTH_CHECK_INTERVAL_S: int = 15
    HEARTBEAT_TTL_S: int = 30
    METRICS_ENABLED: bool = True
    METRICS_PORT: int = 9090
    METRICS_PUBLISH_INTERVAL_S: int = 5

    # ── Redis optimization ────────────────────────────────────────
    REDIS_SOCKET_KEEPALIVE: bool = True
    REDIS_SOCKET_TIMEOUT: int = 5

    class Config:
        env_file = ".env"


@lru_cache()
def get_agent_settings() -> AgentSettings:
    return AgentSettings()
