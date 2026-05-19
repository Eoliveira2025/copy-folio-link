from fastapi import FastAPI, HTTPException
import os
import logging
from typing import List, Dict, Any
from metaapi_cloud_sdk import MetaApi
from copy_factory_api_client import CopyFactory

# This service is the only one allowed to import MetaApi SDK
# It runs in a separate container (ct-metaapi-service)

app = FastAPI(title="MetaApi Proxy Service")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

METAAPI_TOKEN = os.getenv("METAAPI_TOKEN")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/internal/metaapi/accounts/{account_id}")
async def get_account(account_id: str):
    try:
        api = MetaApi(METAAPI_TOKEN)
        account = await api.metatrader_account_api.get_account(account_id)
        return {
            "id": account.id,
            "state": account.state,
            "connectionStatus": account.connection_status,
            "reliability": account.reliability
        }
    except Exception as e:
        logger.error(f"Error getting account {account_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/internal/metaapi/accounts/{account_id}/information")
async def get_account_information(account_id: str):
    try:
        api = MetaApi(METAAPI_TOKEN)
        account = await api.metatrader_account_api.get_account(account_id)
        if account.state != 'DEPLOYED':
             return {"balance": 0, "equity": 0}
             
        # Use streaming to get current metrics
        # This is a simplified version of what the SDK does
        # In production, this would use the synchronized account
        return {
            "balance": getattr(account, 'last_balance', 0),
            "equity": getattr(account, 'last_equity', 0)
        }
    except Exception as e:
        logger.error(f"Error getting account info {account_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/internal/metaapi/accounts/{account_id}/positions")
async def get_positions(account_id: str):
    try:
        api = MetaApi(METAAPI_TOKEN)
        account = await api.metatrader_account_api.get_account(account_id)
        positions = await account.get_positions()
        return [
            {
                "id": p.id,
                "symbol": p.symbol,
                "type": p.type,
                "volume": p.volume,
                "openPrice": p.open_price,
                "time": p.time.isoformat() if hasattr(p.time, 'isoformat') else str(p.time),
                "profit": p.profit
            } for p in positions
        ]
    except Exception as e:
        logger.error(f"Error getting positions for {account_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/internal/metaapi/accounts/{account_id}/positions/{position_id}/close")
async def close_position(account_id: str, position_id: str):
    try:
        api = MetaApi(METAAPI_TOKEN)
        account = await api.metatrader_account_api.get_account(account_id)
        connection = await account.get_rpc_connection()
        await connection.connect()
        await connection.wait_synchronized()
        
        result = await connection.close_position(position_id)
        return {"status": "success", "result": result}
    except Exception as e:
        logger.error(f"Error closing position {position_id} on {account_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
