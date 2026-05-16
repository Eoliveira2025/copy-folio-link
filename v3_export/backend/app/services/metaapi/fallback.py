import logging

logger = logging.getLogger(__name__)

class FallbackService:
    """Handles failover between V1 (Local) and V3 (Cloud MetaApi)."""
    
    async def switch_to_v1(self, user_id, account_id):
        """Switch user from MetaApi to Local Agent."""
        logger.info(f"Switching user {user_id} account {account_id} to V1 fallback")
        return {"version": "v1"}

    async def switch_to_v3(self, user_id, account_id):
        """Switch user from Local Agent to MetaApi Cloud."""
        logger.info(f"Switching user {user_id} account {account_id} to V3")
        return {"version": "v3"}
