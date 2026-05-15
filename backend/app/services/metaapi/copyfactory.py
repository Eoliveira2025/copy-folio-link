import logging
import json
try:
    from metaapi_cloud_sdk import MetaApi
    from metaapi_cloud_copyfactory_sdk import CopyFactory
except ImportError:
    # Fallback to importing from metaapi_cloud_sdk if available there
    from metaapi_cloud_sdk import MetaApi, CopyFactory

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

class CopyFactoryService:
    """Service for CopyFactory (MetaApi) integration."""
    
    def __init__(self, token: str = None):
        self.token = token or settings.METAAPI_TOKEN
        # In newer versions (SDK 29+), CopyFactory is a separate class
        self.cf_api = CopyFactory(self.token) if self.token else None

    async def create_strategy_provider(self, name: str, account_id: str):
        """Create a new strategy provider (Master)."""
        if not self.cf_api:
            raise Exception("MetaApi token not configured")
            
        logger.info(f"Creating CopyFactory strategy provider: {name} for account {account_id}")
        try:
            # 1. Generate a new strategy ID
            # Some versions might use generate_strategy_id, others might just use create_strategy
            # Based on SDK 29.1.1/CopyFactory 12.x, we usually use the configuration_api
            
            # Using generate_strategy_id is safer for PUT/UPDATE logic
            try:
                strategy_id_data = await self.cf_api.configuration_api.generate_strategy_id()
                strategy_id = strategy_id_data['id']
            except AttributeError:
                # Fallback for different SDK versions
                import uuid
                strategy_id = str(uuid.uuid4())

            # 2. Create/Update the strategy
            # Note: The account must have 'PROVIDER' role in MetaApi
            await self.cf_api.configuration_api.update_strategy(strategy_id, {
                'name': name,
                'description': f'Provider for {name}',
                'accountId': account_id
            })
            
            logger.info(f"CopyFactory Strategy created: {strategy_id}")
            return {"strategy_id": strategy_id}
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"CopyFactory SDK Error (create_strategy): {error_msg}")
            # Specific error for missing PROVIDER role
            if "PROVIDER" in error_msg:
                raise Exception(f"MetaApi Error: Account {account_id} must have 'PROVIDER' role enabled in MetaApi dashboard.")
            raise Exception(f"CopyFactory Error: {error_msg}")

    async def subscribe_account(self, subscriber_account_id: str, strategy_id: str, risk_ratio: float = 1.0):
        """Subscribe an account to a strategy."""
        if not self.cf_api:
            raise Exception("MetaApi token not configured")
            
        logger.info(f"Subscribing account {subscriber_account_id} to strategy {strategy_id}")
        try:
            # Enhanced payload for SDK 12.0.0 and CopyFactory v2 compatibility
            payload = {
                'name': f'Subscriber {subscriber_account_id}',
                'accountId': subscriber_account_id, # Critical: link to the MetaApi account
                'enabled': True,                    # Activation state at root level
                'subscriptions': [{
                    'strategyId': strategy_id,
                    'multiplier': risk_ratio,
                    'enabled': True                 # Activation state at subscription level
                }]
            }
            
            logger.debug(f"DEBUG: CopyFactory update_subscriber payload: {json.dumps(payload)}")
            
            # Using update_subscriber for SDK 12.0.0
            await self.cf_api.configuration_api.update_subscriber(subscriber_account_id, payload)
            
            # Verify and log final status
            try:
                subscriber_data = await self.cf_api.configuration_api.get_subscriber(subscriber_account_id)
                logger.debug(f"DEBUG: CopyFactory subscriber created successfully. Data: {json.dumps(subscriber_data)}")
                logger.info(f"Subscriber {subscriber_account_id} is now ACTIVE and linked to strategy {strategy_id}")
            except Exception as ve:
                logger.warning(f"Subscriber updated but verification failed: {ve}")

            return {"subscription_id": strategy_id, "status": "ACTIVE"}
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"CopyFactory SDK Error (subscribe): {error_msg}")
            # Specific error for missing SUBSCRIBER role
            if "SUBSCRIBER" in error_msg:
                raise Exception(f"MetaApi Error: Account {subscriber_account_id} must have 'SUBSCRIBER' role enabled.")
            raise Exception(f"CopyFactory Error: {error_msg}")
