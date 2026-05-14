# 📋 Checklist de Deploy V3 MetaApi - VPS 2

Este guia foi preparado para uma instalação manual e segura, sem afetar a V1 em produção.

## 1. Preparação (Upload)
- [ ] Enviar o arquivo `copytrade-v3-metaapi-deploy.zip` para o VPS 2.
- [ ] Extrair o conteúdo em uma pasta temporária.

## 2. Atualização de Arquivos
Substitua ou adicione os seguintes arquivos no seu diretório do projeto (ex: `/home/user/copytrade-pro`):

**Backend (Serviços e Rotas):**
- [ ] Copiar `backend/app/services/metaapi/` -> `backend/app/services/`
- [ ] Copiar `backend/app/api/routes/metaapi_admin.py` -> `backend/app/api/routes/`
- [ ] **Atenção:** Verifique se `backend/app/api/__init__.py` já importa o `metaapi_admin`. Se não, adicione manualmente.

**Frontend (Painel Admin):**
- [ ] Copiar `src/pages/admin/MetaApiAdmin.tsx` -> `src/pages/admin/`

**Documentação:**
- [ ] Copiar `docs/METAAPI_V3_ARCHITECTURE.md` -> `docs/`
- [ ] Copiar `docs/METAAPI_V3_DEPLOY_VPS2.md` -> `docs/`

## 3. Banco de Dados (Migrations)
Execute o comando SQL contido em `migrations/v3_metaapi.sql` no seu gerenciador de banco de dados (Postgres) ou via terminal:

```bash
psql -h localhost -U postgres -d copytrade -f migrations/v3_metaapi.sql
```

## 4. Configuração de Ambiente (.env)
Edite o arquivo `.env` do backend e adicione as flags (mantendo desativado por enquanto):

```env
# MetaApi V3 Configuration
METAAPI_ENABLED=false
COPYFACTORY_ENABLED=false
METAAPI_TOKEN=COLE_SEU_TOKEN_AQUI
METAAPI_REGION=new-york
```

## 5. Reiniciar Containers
Após atualizar os arquivos, reconstrua e reinicie os containers para aplicar as mudanças de código:

```bash
docker-compose down
docker-compose up -d --build
```

## 6. Testes de Health Check
Verifique se a nova rota da V3 está respondendo (mesmo desativada):

```bash
curl http://localhost:8000/api/v1/admin/metaapi/health
```
*Esperado: `{"status": "ready", "metaapi_enabled": false, ...}`*

## 7. Ativação e Teste Real
1. Altere no `.env`: `METAAPI_ENABLED=true` e `COPYFACTORY_ENABLED=true`.
2. Reinicie: `docker-compose restart backend`.
3. Acesse o painel Admin no navegador: `/admin/metaapi`.
4. Conecte uma conta Master Demo e uma Cliente Demo para testar a cópia.

---
**Caso algo dê errado:**
- Volte as flags no `.env` para `false`.
- Reinicie o container: `docker-compose restart backend`.
- A V1 continuará funcionando normalmente.
