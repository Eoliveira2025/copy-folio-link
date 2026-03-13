"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_NAME: str = "CopyTrade Pro API"
    DEBUG: bool = False
    API_PREFIX: str = "/api/v1"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/copytrade"
    DATABASE_URL_SYNC: str = "postgresql://postgres:postgres@localhost:5432/copytrade"

    # Auth
    SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Encryption key for MT5 credentials (Fernet)
    MT5_CREDENTIAL_KEY: str = "change-me-32-byte-base64-key===="

    # Payment gateways
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    ASAAS_API_KEY: str = ""
    MERCADOPAGO_ACCESS_TOKEN: str = ""

    # Free trial
    FREE_TRIAL_DAYS: int = 30
    INVOICE_GENERATE_BEFORE_DAYS: int = 10
    INVOICE_DUE_AFTER_DAYS: int = 2
    BLOCK_AFTER_OVERDUE_DAYS: int = 2

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
