"""Engine configuration — tuned for ultra-low-latency trade streaming."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class EngineSettings(BaseSettings):
    REDIS_URL: str = "redis://localhost:6379/0"
    DATABASE_URL_SYNC: str = "postgresql://postgres:postgres@localhost:5432/copytrade"
    MT5_CREDENTIAL_KEY: str = "change-me-32-byte-base64-key===="

    # ── Master Listener (ultra-fast polling) ──────────────────────
    MASTER_POLL_INTERVAL_MS: int = 10  # 10ms polling (100 polls/sec)
    POSITION_POLL_INTERVAL_MS: int = 10  # Position snapshot diff interval
    ORDER_HISTORY_POLL_INTERVAL_MS: int = 50  # Order history check (less frequent)
    LISTENER_USE_ORDERS_HISTORY: bool = True  # Also monitor orders (not just positions)

    # ── Health ────────────────────────────────────────────────────
    HEALTH_CHECK_INTERVAL_S: int = 15
    HEARTBEAT_TTL_S: int = 30

    # ── Execution ─────────────────────────────────────────────────
    MAX_RETRY_ATTEMPTS: int = 3
    RETRY_BASE_DELAY_MS: int = 100  # Exponential: 100ms, 200ms, 400ms
    EXECUTION_TIMEOUT_S: int = 5

    # ── Slippage control ──────────────────────────────────────────
    MAX_SLIPPAGE_POINTS: int = 30  # Default max slippage
    SLIPPAGE_REJECT_ENABLED: bool = True  # Reject orders exceeding max slippage

    # ── Workers ───────────────────────────────────────────────────
    WORKER_COUNT: int = 64  # Parallel execution workers (env: COPY_ENGINE_WORKERS)

    class Config:
        env_file = ".env"
        fields = {
            "WORKER_COUNT": {"env": ["COPY_ENGINE_WORKERS", "WORKER_COUNT"]},
        }
    DISTRIBUTOR_THREAD_POOL_SIZE: int = 16  # Concurrent fan-out threads
    EXECUTOR_BATCH_SIZE: int = 10  # Process up to N orders per batch pop

    # ── Lot calculation ───────────────────────────────────────────
    MIN_LOT: float = 0.01
    MAX_LOT: float = 100.0
    LOT_STEP: float = 0.01

    # ── Metrics ───────────────────────────────────────────────────
    METRICS_ENABLED: bool = True
    METRICS_PORT: int = 9090  # Prometheus metrics HTTP port
    METRICS_PUBLISH_INTERVAL_S: int = 5  # Publish to Redis for dashboard

    # ── Redis optimization ────────────────────────────────────────
    REDIS_SOCKET_KEEPALIVE: bool = True
    REDIS_SOCKET_TIMEOUT: int = 5
    REDIS_CONNECTION_POOL_SIZE: int = 50

    # Note: Config class defined above with WORKER_COUNT env alias


@lru_cache()
def get_engine_settings() -> EngineSettings:
    return EngineSettings()
