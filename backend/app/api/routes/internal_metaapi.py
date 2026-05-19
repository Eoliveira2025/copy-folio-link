from fastapi import APIRouter, HTTPException, Path
from typing import List, Dict, Any
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# This router should ONLY be active in the ct-metaapi-service container
# which has the metaapi-cloud-sdk installed.

def get_sdk_client():
    """
    Lazy import and initialization of the MetaApi SDK.
    This prevents ct-api from crashing if the SDK is not installed.
    """
    try:
        from metaapi_cloud_sdk import MetaApi
        from app.core.config import get_settings
        settings = get_settings()
        if not settings.METAAPI_TOKEN:
            raise Exception("METAAPI_TOKEN not configured")
        return MetaApi(settings.METAAPI_TOKEN)
    except ImportError:
        logger.error("metaapi-cloud-sdk is not installed. This route requires the SDK.")
        raise HTTPException(status_code=500, detail="MetaApi SDK not installed on this service instance")
    except Exception as e:
        logger.error(f"Error initializing MetaApi SDK: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/accounts/{account_id}/positions")
async def get_internal_positions(
    account_id: str = Path(..., description="MetaApi Account ID")
):
    """
    INTERNAL ENDPOINT: Fetch real-time positions directly from MetaApi SDK.
    """
    api = get_sdk_client()
    try:
        account = await api.metatrader_api.get_account(account_id)
        # Wait for account to be deployed/synchronized if needed
        # In a real scenario, the service should keep these accounts synchronized
        connection = await account.get_streaming_connection()
        if not connection.terminal_state.connected:
            await connection.connect()
            await connection.wait_synchronized()
            
        positions = connection.terminal_state.positions
        return positions
    except Exception as e:
        logger.error(f"Error fetching positions for {account_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/accounts/{account_id}/positions/{position_id}/close")
async def close_internal_position(
    account_id: str = Path(...),
    position_id: str = Path(...)
):
    """
    INTERNAL ENDPOINT: Close a position via MetaApi SDK.
    """
    api = get_sdk_client()
    try:
        account = await api.metatrader_api.get_account(account_id)
        connection = await account.get_streaming_connection()
        if not connection.terminal_state.connected:
            await connection.connect()
            await connection.wait_synchronized()
            
        result = await connection.close_position(position_id)
        return {"status": "SUCCESS", "result": result}
    except Exception as e:
        logger.error(f"Error closing position {position_id} on {account_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/accounts/{account_id}")
async def get_internal_account(account_id: str = Path(...)):
    """INTERNAL: Get account status."""
    api = get_sdk_client()
    try:
        account = await api.metatrader_api.get_account(account_id)
        return {
            "id": account.id,
            "connection_status": account.connection_status,
            "deployment_status": account.deployment_status
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/accounts/{account_id}/information")
async def get_internal_account_info(account_id: str = Path(...)):
    """INTERNAL: Get account balance/equity."""
    api = get_sdk_client()
    try:
        account = await api.metatrader_api.get_account(account_id)
        connection = await account.get_streaming_connection()
        if not connection.terminal_state.connected:
            await connection.connect()
            await connection.wait_synchronized()
            
        account_info = connection.terminal_state.account_information
        return account_info
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
