import logging
import asyncio
from typing import Optional, List, Dict, Any
from metaapi_cloud_sdk import MetaApi
from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

class MetaApiClient:
    """Client for MetaApi integration using official SDK."""
    
    def __init__(self, token: str = None):
        self.token = token or settings.METAAPI_TOKEN
        if not self.token:
            logger.error("METAAPI_TOKEN not configured!")
        self.api = MetaApi(self.token) if self.token else None
        
    async def create_account(self, name: str, login: str, server: str, password: str, platform: str = "mt5"):
        """Create a new MetaApi account."""
        if not self.api:
            raise Exception("MetaApi token not configured")
        
        logger.info(f"Creating MetaApi account for {login} on {server}")
        try:
            provisioning_api = self.api.provisioning_api
            account = await provisioning_api.create_account({
                'name': name,
                'type': 'cloud',
                'login': login,
                'password': password,
                'server': server,
                'platform': platform,
                'magic': 123456, # Default magic
                'region': settings.METAAPI_REGION
            })
            return {'id': account.id, 'status': 'CREATED'}
        except Exception as e:
            logger.error(f"MetaApi SDK Error (create_account): {e}")
            raise e

    async def deploy_account(self, account_id: str):
        """Deploy (provision) a MetaApi account."""
        if not self.api:
            raise Exception("MetaApi token not configured")
        
        logger.info(f"Deploying MetaApi account {account_id}")
        try:
            account = await self.api.provisioning_api.get_account(account_id)
            await account.deploy()
            return {"status": "DEPLOYING"}
        except Exception as e:
            logger.error(f"MetaApi SDK Error (deploy_account): {e}")
            raise e

    async def undeploy_account(self, account_id: str):
        """Undeploy a MetaApi account to save resources."""
        if not self.api:
            raise Exception("MetaApi token not configured")
        
        logger.info(f"Undeploying MetaApi account {account_id}")
        try:
            account = await self.api.provisioning_api.get_account(account_id)
            await account.undeploy()
            return {"status": "UNDEPLOYED"}
        except Exception as e:
            logger.error(f"MetaApi SDK Error (undeploy_account): {e}")
            raise e

    async def remove_account(self, account_id: str):
        """Remove an account from MetaApi."""
        if not self.api:
            raise Exception("MetaApi token not configured")
        
        logger.info(f"Removing MetaApi account {account_id}")
        try:
            account = await self.api.provisioning_api.get_account(account_id)
            await account.remove()
            return {"status": "REMOVED"}
        except Exception as e:
            logger.error(f"MetaApi SDK Error (remove_account): {e}")
            raise e

    async def get_account(self, account_id: str):
        """Get account details from MetaApi."""
        if not self.api:
            return {"error": "MetaApi token not configured"}
            
        try:
            account = await self.api.provisioning_api.get_account(account_id)
            return {
                "id": account.id, 
                "connectionStatus": account.connection_status,
                "deploymentStatus": account.deployment_status
            }
        except Exception as e:
            logger.error(f"MetaApi SDK Error (get_account): {e}")
            return {"error": str(e)}
