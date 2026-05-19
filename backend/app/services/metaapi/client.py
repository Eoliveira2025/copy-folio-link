import logging
import httpx
from typing import Optional, List, Dict, Any
from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# Base URL for the isolated metaapi-service
METAAPI_SERVICE_URL = "http://ct-metaapi-service:8010"

class MetaApiClient:
    """HTTP Client for MetaApi integration via the isolated ct-metaapi-service."""
    
    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout
        
    async def _get(self, path: str, params: Dict = None) -> Any:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(f"{METAAPI_SERVICE_URL}{path}", params=params)
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.error(f"MetaApi Service GET Error ({path}): {e}")
            raise e

    async def _post(self, path: str, json_data: Dict = None) -> Any:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(f"{METAAPI_SERVICE_URL}{path}", json=json_data)
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.error(f"MetaApi Service POST Error ({path}): {e}")
            raise e

    async def create_account(self, name: str, login: str, server: str, password: str, platform: str = "mt5", roles: List[str] = None):
        return await self._post("/internal/metaapi/accounts", {
            "name": name,
            "login": login,
            "server": server,
            "password": password,
            "platform": platform,
            "roles": roles
        })

    async def deploy_account(self, account_id: str):
        return await self._post(f"/internal/metaapi/accounts/{account_id}/deploy")

    async def get_account(self, account_id: str):
        return await self._get(f"/internal/metaapi/accounts/{account_id}")

    async def get_account_information(self, account_id: str):
        return await self._get(f"/internal/metaapi/accounts/{account_id}/information")

    async def get_positions(self, account_id: str):
        return await self._get(f"/internal/metaapi/accounts/{account_id}/positions")

    async def close_position(self, account_id: str, position_id: str):
        return await self._post(f"/internal/metaapi/accounts/{account_id}/positions/{position_id}/close")

    async def remove_account(self, account_id: str):
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.delete(f"{METAAPI_SERVICE_URL}/internal/metaapi/accounts/{account_id}")
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.error(f"MetaApi Service DELETE Error: {e}")
            raise e
