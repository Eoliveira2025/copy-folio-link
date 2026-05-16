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
        
    async def create_account(self, name: str, login: str, server: str, password: str, platform: str = "mt5", roles: List[str] = None):
        """Create a new MetaApi account."""
        if not self.api:
            raise Exception("MetaApi token not configured")
        
        logger.info(f"Creating MetaApi account for {login} on {server}")
        try:
            account_api = self.api.metatrader_account_api
            account = await account_api.create_account({
                'name': name,
                'type': 'cloud',
                'login': login,
                'password': password,
                'server': server,
                'platform': platform,
                'magic': 123456, 
                'region': settings.METAAPI_REGION,
                'quoteStreamingIntervalInSeconds': 2.5,
                'copyFactoryRoles': roles or ['PROVIDER', 'SUBSCRIBER'] # Default to both for flexibility
            })
            return {'id': account.id, 'status': 'CREATED'}
        except Exception as e:
            logger.error(f"MetaApi SDK Error (create_account): {e}")
            if "Authentication failed" in str(e):
                raise Exception(f"MetaApi Error: Invalid Credentials - {e}")
            raise e

    async def deploy_account(self, account_id: str):
        """Deploy (provision) a MetaApi account."""
        if not self.api:
            raise Exception("MetaApi token not configured")
        
        logger.info(f"Deploying MetaApi account {account_id}")
        try:
            account = await self.api.metatrader_account_api.get_account(account_id)
            await account.deploy()
            return {"status": "DEPLOYING"}
        except Exception as e:
            logger.error(f"MetaApi SDK Error (deploy_account): {e}")
            raise e

    async def wait_until_connected(self, account_id: str, timeout: int = 60):
        """Wait until account is connected."""
        if not self.api:
            return
            
        try:
            account = await self.api.metatrader_account_api.get_account(account_id)
            await account.wait_connected(timeout)
            return {"status": "CONNECTED"}
        except Exception as e:
            logger.error(f"Timeout waiting for connection {account_id}: {e}")
            return {"status": "TIMEOUT", "error": str(e)}

    async def undeploy_account(self, account_id: str):
        """Undeploy a MetaApi account to save resources."""
        if not self.api:
            raise Exception("MetaApi token not configured")
        
        logger.info(f"Undeploying MetaApi account {account_id}")
        try:
            account = await self.api.metatrader_account_api.get_account(account_id)
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
            account = await self.api.metatrader_account_api.get_account(account_id)
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
            account = await self.api.metatrader_account_api.get_account(account_id)
            # Official SDK 29.1.1 properties:
            # state: CREATED, DEPLOYING, DEPLOYED, etc.
            # connection_status: CONNECTED, DISCONNECTED, DISCONNECTED_FROM_BROKER
            state = getattr(account, 'state', 'UNKNOWN')
            conn_status = getattr(account, 'connection_status', 'UNKNOWN')
            
            return {
                "id": account.id, 
                "connectionStatus": conn_status,
                "deploymentStatus": state, # Map 'state' to 'deploymentStatus' for backward compatibility
                "state": state,
                "connection_status": conn_status,
                "deployment_status": state,
                "connected": conn_status == 'CONNECTED'
            }
        except Exception as e:
            logger.error(f"MetaApi SDK Error (get_account): {e}")
            return {"error": str(e)}

    async def get_account_information(self, account_id: str):
        """Get account metrics (balance, equity, margin, etc.)."""
        if not self.api:
            return None
        try:
            account = await self.api.metatrader_account_api.get_account(account_id)
            if account.state != 'DEPLOYED' or account.connection_status != 'CONNECTED':
                return None
            
            connection = account.get_rpc_connection()
            await connection.connect()
            await connection.wait_synchronized()
            
            account_info = await connection.get_account_information()
            return account_info
        except Exception as e:
            logger.error(f"Error fetching account information for {account_id}: {e}")
            return None

    async def get_positions(self, account_id: str):
        """Get open positions for an account."""
        if not self.api:
            return []
        try:
            account = await self.api.metatrader_account_api.get_account(account_id)
            if account.state != 'DEPLOYED' or account.connection_status != 'CONNECTED':
                return []
            
            connection = account.get_rpc_connection()
            await connection.connect()
            await connection.wait_synchronized()
            
            positions = await connection.get_positions()
            return positions
        except Exception as e:
            logger.error(f"Error fetching positions for {account_id}: {e}")
            return []

    async def close_position(self, account_id: str, position_id: str):
        """Close a specific position."""
        if not self.api:
            raise Exception("MetaApi token not configured")
        try:
            account = await self.api.metatrader_account_api.get_account(account_id)
            connection = account.get_rpc_connection()
            await connection.connect()
            await connection.wait_synchronized()
            
            # Close by position id
            result = await connection.close_position(position_id)
            return result
        except Exception as e:
            logger.error(f"Error closing position {position_id} on {account_id}: {e}")
            raise e
