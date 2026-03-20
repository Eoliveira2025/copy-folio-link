"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_NAME: str = "CopyTrade Pro API"
    DEBUG: bool = False
    API_PREFIX: str = "/api/v1"
    ENVIRONMENT: str = "development"  # development | production

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

    # Asaas
    ASAAS_ENABLED: bool = True
    ASAAS_API_KEY: str = ""
    ASAAS_ENVIRONMENT: str = "sandbox"  # sandbox | production
    ASAAS_SANDBOX: bool = True  # Alias: True = sandbox, False = production
    ASAAS_BASE_URL: str = ""  # Override; leave empty to auto-detect from ASAAS_SANDBOX
    ASAAS_WEBHOOK_TOKEN: str = ""
    ASAAS_WEBHOOK_ENABLED: bool = True
    ASAAS_TIMEOUT_SECONDS: int = 30
    ASAAS_BILLING_DUE_DAYS: int = 1  # Days until due date for new charges
    MERCADOPAGO_ACCESS_TOKEN: str = ""
    CELCOIN_CLIENT_ID: str = ""
    CELCOIN_CLIENT_SECRET: str = ""

    # Free trial
    FREE_TRIAL_DAYS: int = 30
    INVOICE_GENERATE_BEFORE_DAYS: int = 10
    INVOICE_DUE_AFTER_DAYS: int = 2
    BLOCK_AFTER_OVERDUE_DAYS: int = 2

    # Subscription pricing
    SUBSCRIPTION_PRICE: float = 49.90
    SUBSCRIPTION_CURRENCY: str = "USD"

    # Rate limiting
    LOGIN_RATE_LIMIT: int = 5  # max attempts per window
    LOGIN_RATE_WINDOW: int = 300  # 5 minutes

    # CORS
    ALLOWED_ORIGINS: str = ""  # Comma-separated origins, e.g. "https://app.example.com,https://admin.example.com"

    # SMTP / Email
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""

    # Frontend URL (for reset links)
    FRONTEND_URL: str = "http://localhost:5173"

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
