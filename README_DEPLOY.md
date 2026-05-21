# INSTRUÇÕES DE DEPLOY - METAAPI ACCOUNT SYNC (SAFE UPDATE)

Este pacote contém a atualização para sincronização de métricas de contas MetaApi (Balance, Equity, Margin, etc.).

## Conteúdo do Pacote

1. `backend/app/workers/metaapi_account_sync_worker.py`: Worker que executa a cada 5 minutos.
2. `backend/app/services/metaapi/http_client.py`: Cliente HTTP atualizado com suporte a `get_account_information`.
3. `metaapi-service/patch_account_information.py`: Código para adicionar no `main.py` do serviço isolado.

## Passos para Instalação

### 1. Atualizar o MetaApi Proxy Service (metaapi-service)

Abra o arquivo `metaapi-service/main.py` e adicione a nova rota antes das rotas de posições. 
Você pode usar o conteúdo de `metaapi-service/patch_account_information.py` como referência.

O bloco a ser adicionado é:

```python
@app.get("/internal/metaapi/accounts/{account_id}/account-information")
async def get_internal_account_information(account_id: str):
    logger.info(f"[METAAPI INTERNAL] Fetching detailed account information for {account_id}")
    try:
        account = await api.metatrader_account_api.get_account(account_id)
        
        # Garante que a conta esteja deployada e conectada
        if account.deployment_status != 'DEPLOYED':
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
```

### 2. Adicionar o Novo Worker ao docker-compose

Adicione o seguinte bloco ao seu `docker-compose.yml` (ou similar):

```yaml
  ct-metaapi-account-sync-worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: python -m app.workers.metaapi_account_sync_worker
    restart: always
    env_file:
      - .env
    depends_on:
      - db
      - redis
      - ct-metaapi-service
```

### 3. Reiniciar os Serviços

```bash
docker-compose up -d --build ct-metaapi-service backend ct-metaapi-account-sync-worker
```
