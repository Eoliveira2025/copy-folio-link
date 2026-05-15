# CHECKLIST DEPLOY V3 METAAPI (HOMOLOGAÇÃO)

Este guia é para implantar a V3 do CopyTrade Pro (MetaApi) de forma isolada da V1.

## 1. Preparação (Upload)
- [ ] Envie o arquivo `copytrade-v3-metaapi-deploy-full.zip` para o seu VPS 2.
- [ ] Extraia o conteúdo em uma nova pasta, ex: `C:\copytrade_v3` ou `/opt/copytrade_v3`.

## 2. Configuração (.env)
- [ ] Copie o `.env.example` para `.env`.
- [ ] Edite o `.env` e configure:
  - `POSTGRES_PASSWORD`: Escolha uma senha forte.
  - `METAAPI_ENABLED=false` (Mantenha false até o primeiro boot).
  - `COPYFACTORY_ENABLED=false` (Mantenha false até o primeiro boot).

## 3. Comandos de Instalação/Deploy
Abra o terminal na pasta do projeto e execute:

```bash
# Dar permissão de execução aos scripts (se estiver no Linux)
chmod +x scripts/*.sh

# Subir os containers da V3
./scripts/deploy_v3.sh
```

## 4. Verificação de Saúde (Health Check)
Acesse no navegador do VPS ou via `curl`:
- [ ] Principal: `http://localhost:8003/health` -> deve retornar `{"status": "ok"}`
- [ ] MetaApi: `http://localhost:8003/health/metaapi` -> deve retornar `{"status": "disabled"}`
- [ ] CopyFactory: `http://localhost:8003/health/copyfactory` -> deve retornar `{"status": "disabled"}`

## 5. Ativação da MetaApi (Feature Flag)
Após confirmar que os containers estão UP:
- [ ] Edite o `.env`.
- [ ] Configure `METAAPI_TOKEN=seu_token_aqui`.
- [ ] Altere `METAAPI_ENABLED=true`.
- [ ] Altere `COPYFACTORY_ENABLED=true`.
- [ ] Reinicie o container da API:
  ```bash
  docker-compose -f docker-compose.v3.yml restart ctv3-api
  ```

## 6. Teste de Conexão MetaApi
Execute o comando abaixo para testar se a API consegue falar com a MetaApi:
```bash
docker exec -it ctv3-api python -c "from app.services.metaapi.client import MetaApiClient; import asyncio; from app.core.config import get_settings; async def test(): client = MetaApiClient(get_settings().METAAPI_TOKEN); print(await client.health_check()); asyncio.run(test())"
```

## 7. Conectar Contas Demo
(Use o Postman ou a documentação Swagger em `http://localhost:8003/docs`)

1. **Master Demo**:
   - Endpoint: `POST /api/v3/admin/metaapi/accounts`
   - Payload: `{ "account_id": "...", "type": "master" }`
2. **Cliente Demo**:
   - Endpoint: `POST /api/v3/admin/metaapi/accounts`
   - Payload: `{ "account_id": "...", "type": "slave" }`

## 8. Como Voltar Atrás (Rollback)
Se algo der errado e você quiser remover tudo da V3:
```bash
docker-compose -f docker-compose.v3.yml down -v
```
Isso não afetará a V1, pois os nomes dos containers e volumes são diferentes.
