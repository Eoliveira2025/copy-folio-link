"""Bridge Auditor configuration."""

from functools import lru_cache
from pydantic_settings import BaseSettings


class BridgeAuditorSettings(BaseSettings):
    BRIDGE_AUDITOR_ENABLED: bool = False
    BRIDGE_AUDITOR_DELAY_SECONDS: int = 3
    BRIDGE_AUDITOR_RETRY_ATTEMPTS: int = 3
    BRIDGE_AUDITOR_RETRY_INTERVAL_SECONDS: int = 5
    BRIDGE_AUDITOR_AUTO_FIX_ENABLED: bool = False
    BRIDGE_AUDITOR_CLOSE_ORPHAN_POSITIONS: bool = True
    BRIDGE_AUDITOR_ALERT_ON_FAILURE: bool = True

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_auditor_settings() -> BridgeAuditorSettings:
    return BridgeAuditorSettings()
