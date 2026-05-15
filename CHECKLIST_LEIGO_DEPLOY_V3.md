# CHECKLIST DEPLOY V3 (SQLite - Homologação sem Docker)

Este guia é para você configurar a V3 do CopyTrade Pro no seu VPS 2 usando SQLite local, sem depender de Postgres.

## 1. Preparação dos Arquivos
- Certifique-se de que os novos arquivos foram enviados para a pasta `backend/` no seu VPS 2.
- Arquivos importantes:
  - `backend/requirements.v3.txt` (agora inclui aiosqlite e alembic)
  - `backend/app/core/database.py` (adaptado para SQLite)
  - `backend/scripts/create_sqlite_v3.ps1`
  - `backend/scripts/run_migrations_sqlite_v3.ps1`

## 2. Instalação de Dependências
Abra o PowerShell na pasta `backend` e rode:
```powershell
pip install -r requirements.v3.txt
```

## 3. Configuração do Ambiente (.env)
1. Renomeie (ou crie) o arquivo `.env` na pasta `backend` (baseado no `.env.v3.example`):
   ```powershell
   # No PowerShell dentro da pasta backend:
   Copy-Item .env.v3.example .env -Force
   ```
2. Edite o `.env` e configure suas chaves:
   - `METAAPI_TOKEN`: Seu token da MetaApi
   - `METAAPI_ENABLED=true`
   - `COPYFACTORY_ENABLED=true`
   - `DATABASE_URL=sqlite+aiosqlite:///./copytrade_v3.db`
   - `DATABASE_URL_SYNC=sqlite:///./copytrade_v3.db`

## 4. Inicialização do Banco de Dados (SQLite)
Você tem duas opções (recomendamos a Opção A para primeiro teste rápido):

**Opção A: Criação Direta (Mais simples)**
```powershell
.\scripts\create_sqlite_v3.ps1
```
Isso criará o arquivo `copytrade_v3.db` com todas as tabelas necessárias.

**Opção B: Via Migrations Alembic (Padrão de produção)**
```powershell
.\scripts\run_migrations_sqlite_v3.ps1
```

## 5. Iniciando a API
Ainda na pasta `backend`, inicie o servidor:
```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8003 --reload
```
*A porta 8003 é usada para não conflitar com a V1 se ela estiver rodando.*

## 6. Testes de Health Check
Abra o navegador ou use o `curl` no VPS:
- Health Geral: `http://localhost:8003/health`
- Health MetaApi: `http://localhost:8003/health/metaapi`
- Health CopyFactory: `http://localhost:8003/health/copyfactory`

## 7. Como voltar atrás (Rollback)
Se algo der errado:
1. Pare o processo do Python (Ctrl+C).
2. Se quiser limpar tudo da V3, apague o arquivo `copytrade_v3.db`.
3. A V1 continua intacta pois usa seu próprio banco de dados Postgres e suas próprias portas de serviço.

---
**IMPORTANTE:** O SQLite é recomendado apenas para testes de homologação no VPS 2. Para produção com alto volume, recomendamos voltar para o Postgres (basta alterar as URLs no `.env`).
