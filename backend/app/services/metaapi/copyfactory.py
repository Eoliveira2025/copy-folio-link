import logging
from metaapi_cloud_sdk import MetaApi
from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

class CopyFactoryService:
    """Service for CopyFactory (MetaApi) integration."""
    
    def __init__(self, token: str = None):
        self.token = token or settings.METAAPI_TOKEN
        self.api = MetaApi(self.token) if self.token else None

    async def create_strategy_provider(self, name: str, account_id: str):
        """Create a new strategy provider (Master)."""
        if not self.api:
            raise Exception("MetaApi token not configured")
            
        logger.info(f"Creating CopyFactory strategy provider: {name}")
        try:
            copy_factory = self.api.copy_factory_api
            strategy = await copy_factory.configuration_api.create_strategy({
                'name': name,
                'description': f'Provider for {name}',
                'accountId': account_id
            })
            return {"strategy_id": strategy.id}
        except Exception as e:
            logger.error(f"CopyFactory SDK Error (create_strategy): {e}")
            raise e

    async def subscribe_account(self, subscriber_account_id: str, strategy_id: str, risk_ratio: float = 1.0):
        """Subscribe an account to a strategy."""
        if not self.api:
            raise Exception("MetaApi token not configured")
            
        logger.info(f"Subscribing account {subscriber_account_id} to strategy {strategy_id}")
        try:
            copy_factory = self.api.copy_factory_api
            subscription = await copy_factory.configuration_api.update_subscriber_configuration(subscriber_account_id, {
                'subscriptions': [{
                    'strategyId': strategy_id,
                    'multiplier': risk_ratio
                }]
            })
            return {"subscription_id": strategy_id} # CopyFactory subscriptions are often identified by strategyId in simplistic maps
        except Exception as e:
            logger.error(f"CopyFactory SDK Error (subscribe): {e}")
            raise e
