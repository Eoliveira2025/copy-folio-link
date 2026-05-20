from fastapi import FastAPI, HTTPException
import os
import logging
import asyncio
from typing import List, Dict, Any
from metaapi_cloud_sdk import MetaApi
from datetime import datetime

# Configuração de logs para atender aos requisitos institucionais
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger("ct-metaapi-service")

app = FastAPI(title="MetaApi Institutional Proxy Service")

METAAPI_TOKEN = os.getenv("METAAPI_TOKEN")
if not METAAPI_TOKEN:
    logger.error("[METAAPI INTERNAL] CRITICAL: METAAPI_TOKEN not found in environment")

# Instância global do MetaApi SDK
api = MetaApi(METAAPI_TOKEN)

@app.get("/health")
def health():
    return {"status": "ok", "service": "ct-metaapi-service"}

@app.get("/internal/metaapi/accounts/{account_id}")
async def get_account(account_id: str):
    logger.info(f"[METAAPI INTERNAL] Fetching account details for {account_id}")
    try:
        account = await api.metatrader_account_api.get_account(account_id)
        return {
            "id": account.id,
            "state": account.state,
            "connectionStatus": account.connection_status,
            "reliability": account.reliability
        }
    except Exception as e:
        logger.error(f"[METAAPI INTERNAL] Error getting account {account_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/internal/metaapi/accounts/{account_id}/information")
async def get_account_information(account_id: str):
    logger.info(f"[METAAPI INTERNAL] Fetching account information for {account_id}")
    try:
        account = await api.metatrader_account_api.get_account(account_id)
        if account.state != 'DEPLOYED':
             return {"balance": 0, "equity": 0}
             
        # Tenta obter métricas recentes se disponíveis
        return {
            "balance": getattr(account, 'last_balance', 0),
            "equity": getattr(account, 'last_equity', 0)
        }
    except Exception as e:
        logger.error(f"[METAAPI INTERNAL] Error getting account info {account_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/internal/metaapi/accounts/{account_id}/positions")
async def get_positions(account_id: str):
    logger.info(f"[METAAPI INTERNAL] [POSITIONS] Requesting positions for account {account_id}")
    try:
        account = await api.metatrader_account_api.get_account(account_id)
        
        # Obtém conexão RPC para dados em tempo real
        connection = account.get_rpc_connection()
        await connection.connect()
        await connection.wait_synchronized()
        logger.info(f"[METAAPI INTERNAL] [RPC CONNECTED] Synchronized for account {account_id}")
        
        positions = await connection.get_positions()
        
        # Formata o retorno conforme especificação institucional
        formatted_positions = []
        for p in positions:
            formatted_positions.append({
                "id": p['id'],
                "symbol": p['symbol'],
                "type": p['type'],
                "volume": float(p['volume']),
                "profit": float(p['profit']),
                "openTime": p['time'] if isinstance(p['time'], str) else p['time'].isoformat(),
                "magic": p.get('magic', 0)
            })
            
        return formatted_positions
    except Exception as e:
        logger.error(f"[METAAPI INTERNAL] [POSITIONS] Error fetching positions for {account_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/internal/metaapi/accounts/{account_id}/positions/{position_id}/close")
async def close_position(account_id: str, position_id: str):
    logger.info(f"[METAAPI INTERNAL] [CLOSE POSITION] Request to close {position_id} on account {account_id}")
    try:
        account = await api.metatrader_account_api.get_account(account_id)
        
        # Obtém conexão RPC para execução
        connection = account.get_rpc_connection()
        await connection.connect()
        await connection.wait_synchronized()
        logger.info(f"[METAAPI INTERNAL] [RPC CONNECTED] Ready to execute close for {position_id}")
        
        # Executa o fechamento
        # A MetaApi costuma retornar o trade result
        await connection.close_position(position_id)
        
        logger.info(f"[METAAPI INTERNAL] [CLOSE POSITION] Successfully closed {position_id}")
        return {"success": true}
        
    except Exception as e:
        logger.error(f"[METAAPI INTERNAL] [CLOSE POSITION] Error closing position {position_id}: {str(e)}")
        # Se for um erro de "não encontrado", pode ser que já tenha sido fechado
        if "POSITION_NOT_FOUND" in str(e).upper():
            return {"success": true, "note": "position already closed or not found"}
            
        raise HTTPException(status_code=500, detail=str(e))
