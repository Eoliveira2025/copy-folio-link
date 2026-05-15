# V3 Update Guide - Windows VPS 2

Este guia explica como substituir os arquivos e atualizar o ambiente V3 no seu Windows VPS 2 (Sem Docker).

## 1. Preparação
Certifique-se de que a V3 está parada no seu VPS 2.

## 2. Substituição de Arquivos
Substitua os seguintes arquivos/pastas no seu diretório de instalação (`C:\copytrade-v3` ou similar):

*   `backend/app/api/routes/metaapi_admin.py` (Novos endpoints reais)
*   `backend/app/services/metaapi/` (Integração com SDK corrigida)
*   `backend/app/models/metaapi.py` (Novas tabelas se houver)
*   `requirements.v3.txt` (Dependências atualizadas)

## 3. Atualizar Dependências (PowerShell)
Execute no terminal PowerShell dentro da pasta `backend`:

```powershell
python -m venv venv_v3
.\venv_v3\Scripts\activate
pip install -r ..\requirements.v3.txt
```

## 4. Executar Migrações do Banco de Dados
Garantir que as tabelas `metaapi_accounts`, `metaapi_subscriptions` e `metaapi_events` existem:

```powershell
# Usando o script fornecido
powershell -ExecutionPolicy Bypass -File ..\scripts\create_sqlite_v3.ps1
# (Mesmo usando Postgres, este script valida a conexão se configurado no .env)
```

## 5. Iniciar a API V3
```powershell
.\venv_v3\Scripts\activate
$env:METAAPI_ENABLED="true"
$env:COPYFACTORY_ENABLED="true"
uvicorn app.main:app --host 0.0.0.0 --port 8003 --reload
```

## 6. Testar Endpoints (Curl)
```powershell
# Health Check Real
curl http://localhost:8003/api/v1/admin/metaapi/health

# Status da Conexão
curl http://localhost:8003/api/v1/admin/metaapi/status
```
