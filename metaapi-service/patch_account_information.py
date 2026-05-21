# Adicione este bloco no metaapi-service/main.py

@app.get("/internal/metaapi/accounts/{account_id}/account-information")
async def get_internal_account_information(account_id: str):
    logger.info(f"[METAAPI INTERNAL] Fetching detailed account information for {account_id}")
    try:
        account = await api.metatrader_account_api.get_account(account_id)
        
        # Ensure deploy/connect if necessary
        if account.deployment_status != 'DEPLOYED':
            logger.info(f"[METAAPI INTERNAL] Account {account_id} not deployed. Deploying...")
            await account.deploy()
            await account.wait_deployed()
            
        connection = account.get_rpc_connection()
        if not connection.connected:
            await connection.connect()
            await connection.wait_synchronized()
            
        account_info = await connection.get_account_information()
        
        return {
            "balance": account_info.get('balance', 0),
            "equity": account_info.get('equity', 0),
            "margin": account_info.get('margin', 0),
            "free_margin": account_info.get('freeMargin', 0),
            "profit": account_info.get('profit', 0),
            "currency": account_info.get('currency', 'USD'),
            "server": account.server,
            "login": account.login,
            "broker": account.broker
        }
    except Exception as e:
        logger.error(f"[METAAPI INTERNAL] Error getting account info for {account_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
