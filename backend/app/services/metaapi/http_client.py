import logging
import httpx
from typing import Optional, List, Dict, Any
from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# Base URL for the isolated metaapi-service
# In the isolated architecture, this service runs on a different port/container
METAAPI_SERVICE_URL = "http://ct-metaapi-service:8010"

class HttpMetaApiClient:
    """
    Isolated HTTP Client for MetaApi.
    Does NOT import metaapi_cloud_sdk.
    Communicates with ct-metaapi-service via internal Docker network.
    """
    
    def __init__(self, timeout: float = 60.0):
        self.timeout = timeout
        self.base_url = METAAPI_SERVICE_URL
        
    async def _request(self, method: str, path: str, **kwargs) -> Any:
        url = f"{self.base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(method, url, **kwargs)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP Error {e.response.status_code} calling {url}: {e.response.text}")
            raise Exception(f"MetaApi Service Error: {e.response.text}")
        except Exception as e:
            logger.error(f"Error communicating with MetaApi Service at {url}: {e}")
            raise Exception(f"Falha na comunicação com serviço MetaApi: {str(e)}")

    async def get_positions(self, metaapi_account_id: str) -> List[Dict]:
        """Fetch positions from MetaApi via proxy service."""
        return await self._request("GET", f"/internal/metaapi/accounts/{metaapi_account_id}/positions")

    async def close_position(self, metaapi_account_id: str, position_id: str) -> Dict:
        """Close a position via proxy service."""
        return await self._request("POST", f"/internal/metaapi/accounts/{metaapi_account_id}/positions/{position_id}/close")

    async def get_account(self, metaapi_account_id: str) -> Dict:
        """Fetch account status via proxy service."""
        return await self._request("GET", f"/internal/metaapi/accounts/{metaapi_account_id}")

    async def get_account_information(self, metaapi_account_id: str) -> Dict:
        """Fetch account metrics via proxy service."""
        return await self._request("GET", f"/internal/metaapi/accounts/{metaapi_account_id}/information")
