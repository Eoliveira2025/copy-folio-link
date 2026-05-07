"""Bridge feature configuration loaded from environment."""

import os
from functools import lru_cache
from pydantic_settings import BaseSettings


class BridgeSettings(BaseSettings):
    BRIDGE_ENABLED: bool = False
    BRIDGE_TOKEN: str = "change-me"
    BRIDGE_REDIS_CHANNEL_PREFIX: str = "bridge:signal"
    BRIDGE_EXECUTE_QUEUE_PREFIX: str = "bridge:execute"
    BRIDGE_MAX_LOT: float = 100.0
    BRIDGE_MIN_LOT: float = 0.01
    BRIDGE_DEFAULT_LOT_STEP: float = 0.01
    BRIDGE_REQUIRE_ACTIVE_SUBSCRIPTION: bool = True

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_bridge_settings() -> BridgeSettings:
    return BridgeSettings()
