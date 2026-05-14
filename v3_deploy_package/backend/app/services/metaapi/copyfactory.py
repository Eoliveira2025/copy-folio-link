import logging
from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

class CopyFactoryService:
    """Service for CopyFactory (MetaApi) integration."""
    
    def __init__(self, token: str = None):
        self.token = token or settings.METAAPI_TOKEN

    async def create_strategy_provider(self, name: str, account_id: str):
        """Create a new strategy provider (Master)."""
        logger.info(f"Creating CopyFactory strategy provider: {name}")
        return {"strategy_id": "cf_strategy_id"}

    async def update_strategy_provider(self, strategy_id: str, settings: dict):
        """Update strategy provider settings."""
        return {"status": "UPDATED"}

    async def subscribe_account(self, subscriber_account_id: str, strategy_id: str, risk_ratio: float = 1.0):
        """Subscribe an account to a strategy."""
        logger.info(f"Subscribing account {subscriber_account_id} to strategy {strategy_id}")
        return {"subscription_id": "cf_sub_id"}

    async def unsubscribe_account(self, subscription_id: str):
        """Unsubscribe an account from a strategy."""
        return {"status": "UNSUBSCRIBED"}
