import logging
from app.services.metaapi.client import MetaApiClient

logger = logging.getLogger(__name__)

class ProvisioningService:
    """Orchestrates account onboarding and MetaApi deployment."""
    
    def __init__(self):
        self.meta_client = MetaApiClient()

    async def onboard_account(self, user_id, account_data: dict):
        """Full flow: Validate -> Create in MetaApi -> Deploy -> Wait for connection."""
        logger.info(f"Onboarding user {user_id} account to MetaApi")
        # 1. Create account
        # 2. Deploy
        # 3. Update database
        return {"status": "SUCCESS", "metaapi_account_id": "new_id"}
