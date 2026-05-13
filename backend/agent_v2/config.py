"""CopyTrade Pro V2 settings.

Strict isolation from V1: never reuse env keys from `backend/agent/config.py`.
All env vars are prefixed with `V2_` to avoid collisions in production.
"""

from __future__ import annotations

from functools import lru_cache
from pydantic_settings import BaseSettings


class AgentV2Settings(BaseSettings):
    # ── Mode ──────────────────────────────────────────────────────
    POOL_MODE: bool = True  # V2 is always pool-based
    MT5_POOL_V2_ENABLED: bool = False  # Institutional Multi-Account V2

    # ── Institutional Limits ──────────────────────────────────────
    MAX_ACCOUNTS_PER_TERMINAL: int = 50
    MAX_TERMINALS_PER_VPS: int = 20
    MAX_CPU_USAGE_PCT: float = 80.0
    MAX_RAM_USAGE_MB: int = 2048
    MAX_RESTARTS_PER_HOUR: int = 10


    # ── Remote infra (Linux) — separate Redis DB from V1 ──────────
    DATABASE_URL_SYNC: str = "postgresql://postgres:postgres@91.98.20.163:5432/copytrade"
    REDIS_URL: str = "redis://91.98.20.163:6379/2"  # DB /2 (V1 uses /0)
    REDIS_PREFIX: str = "copytrade_v2:"

    # ── Credentials ───────────────────────────────────────────────
    MT5_CREDENTIAL_KEY: str = "change-me-32-byte-base64-key===="

    # ── MT5 Terminal binary ───────────────────────────────────────
    MT5_TERMINAL_PATH: str = r"C:\Program Files\MetaTrader 5\terminal64.exe"
    MT5_BASE_PATH: str = r"C:\Program Files\MetaTrader 5"

    # ── V2 isolated paths ─────────────────────────────────────────
    V2_ROOT: str = r"C:\copytrade_v2"
    V2_MASTERS_DIR: str = r"C:\MT5_Masters_V2"
    V2_POOL_DIR: str = r"C:\MT5_Pool_V2"
    V2_LOGS_DIR: str = r"C:\copytrade_v2_logs"
    V2_INSTANCE_MAPPING_FILE: str = r"C:\MT5_Pool_V2\pools.json"
    MT5_INIT_TIMEOUT_MS: int = 60000

    # ── Pool sizing (segmented per master/strategy) ───────────────
    POOL_CAPACITY: int = 15            # contas por terminal (15 inicial; 20–25 após testes)
    POOL_PREWARM_STANDBY: int = 1      # qtd. de pools STANDBY pré-aquecidos por estratégia
    POOL_AUTOPROVISION_ENABLED: bool = True

    # ── Login / session ───────────────────────────────────────────
    SESSION_LOGIN_TIMEOUT_S: int = 15
    SESSION_STICKY_HOLD_MS: int = 500   # mantém conta logada se houver fila pendente

    # ── Execution safety (DEMO → REAL path) ───────────────────────
    # Modes: DRY_RUN | DEMO_ONLY | LIVE_WHITELIST
    EXECUTION_MODE: str = "DRY_RUN"
    ORDER_EXECUTION_ENABLED: bool = False
    # Comma-separated lists of account_id (UUID) OR login (int)
    LIVE_WHITELIST_ACCOUNTS: str = ""
    DEMO_WHITELIST_ACCOUNTS: str = ""

    # ── Execution ─────────────────────────────────────────────────
    MAX_RETRY_ATTEMPTS: int = 3
    RETRY_BASE_DELAY_MS: int = 100
    MAX_SLIPPAGE_POINTS: int = 30
    SLIPPAGE_REJECT_ENABLED: bool = True

    # Circuit breaker (per pool)
    POOL_CB_FAILURE_THRESHOLD: int = 5      # consecutive failures → FAILED
    POOL_CB_RESET_AFTER_SUCCESS: bool = True

    # Rate limit (per pool, token bucket)
    POOL_RATE_LIMIT_PER_S: float = 20.0
    POOL_RATE_LIMIT_BURST: int = 20

    # ── Lot calculation ───────────────────────────────────────────
    MIN_LOT: float = 0.01
    MAX_LOT: float = 100.0
    LOT_STEP: float = 0.01

    # ── Master polling ────────────────────────────────────────────
    MASTER_POLL_INTERVAL_MS: int = 50
    ORDER_HISTORY_POLL_INTERVAL_MS: int = 100

    # ── DB sync ───────────────────────────────────────────────────
    DB_SYNC_INTERVAL_S: int = 30
    BALANCE_SYNC_INTERVAL_S: int = 60

    # ── Close reconciler ──────────────────────────────────────────
    CLOSE_RECONCILER_ENABLED: bool = True   # V2 default ON
    CLOSE_RECONCILER_MAX_ATTEMPTS: int = 5
    CLOSE_RECONCILER_RETRY_DELAYS_SECONDS: str = "2,5,10,20,30"
    CLOSE_RECONCILER_ACCEPT_MANUAL_CLOSE: bool = True

    # ── Health / metrics ──────────────────────────────────────────
    HEALTH_CHECK_INTERVAL_S: int = 15
    HEARTBEAT_TTL_S: int = 30
    METRICS_ENABLED: bool = True
    METRICS_PORT: int = 9091              # 9090 já usada pela V1
    METRICS_PUBLISH_INTERVAL_S: int = 5

    # ── Watchdog ──────────────────────────────────────────────────
    WATCHDOG_INTERVAL_S: int = 15
    TERMINAL_RESTART_BACKOFF_S: float = 5.0
    MAX_TERMINAL_RESTART_ATTEMPTS: int = 5

    # ── Strategy transition ───────────────────────────────────────
    TRANSITION_POLL_INTERVAL_S: int = 5

    # ── Institutional Upgrades ────────────────────────────────────
    V2_INSTITUTIONAL_SAFE_MODE_ENABLED: bool = False
    V2_PROCESS_RECYCLER_ENABLED: bool = False
    V2_RESOURCE_GUARD_ENABLED: bool = False
    V2_EXECUTION_DEDUP_ENABLED: bool = False
    V2_AUTO_RECOVERY_AFTER_REBOOT: bool = False
    V2_HEARTBEAT_INTERVAL_S: int = 5
    V2_VPS_ID: str = "institutional-01"  # Unique ID for each VPS
    V2_DISTRIBUTED_LOCK_TTL_S: int = 10
    V2_SHADOW_MODE: bool = False        # If true, log but don't execute orders
    V2_ROUTING_VERSION: str = "v2"      # This VPS only executes 'v2' accounts


    # ── Redis tuning ──────────────────────────────────────────────
    REDIS_SOCKET_KEEPALIVE: bool = True
    REDIS_SOCKET_TIMEOUT: int = 5

    class Config:
        env_file = ".env"
        env_prefix = "V2_"
        extra = "ignore"


@lru_cache()
def get_v2_settings() -> AgentV2Settings:
    return AgentV2Settings()
