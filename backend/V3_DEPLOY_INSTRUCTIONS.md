### Deployment V3 MetaApi - Manual Update (Windows VPS 2)

#### 1. Arquivos Novos/Atualizados
Substitua os arquivos no diretório `backend` conforme os comandos abaixo:

```powershell
# Criar diretórios se não existirem
New-Item -ItemType Directory -Force "backend/app/models"
New-Item -ItemType Directory -Force "backend/app/schemas"
New-Item -ItemType Directory -Force "backend/app/services/metaapi"

# Atualizar Modelos (MetaApi Tables)
# [Conteúdo do arquivo backend/app/models/metaapi.py]
# [Conteúdo do arquivo backend/app/models/__init__.py]

# Atualizar Schemas
# [Conteúdo do arquivo backend/app/schemas/metaapi.py]

# Atualizar Services
# [Conteúdo do arquivo backend/app/services/metaapi/service.py]

# Atualizar API Router
# [Conteúdo do arquivo backend/app/api/routes/metaapi_admin.py]
```

#### 2. Rodar Migrations (SQLite ou Postgres)
Se estiver usando SQLite (homologação):
```powershell
python -m scripts.create_sqlite_v3
```

#### 3. Testar Endpoints via PowerShell (curl)

**Verificar Health:**
```powershell
curl http://localhost:8003/api/v1/admin/metaapi/health
```

**Cadastrar Conta Master Demo:**
```powershell
$body = @{
    login = "123456"
    password = "SUA_SENHA"
    server = "Exness-MT5Trial"
    name = "master-demo-v3"
    type = "MASTER"
} | ConvertTo-Json

curl -Method Post -Uri "http://localhost:8003/api/v1/admin/metaapi/accounts" -Body $body -ContentType "application/json" -Headers @{ "Authorization" = "Bearer SEU_TOKEN_ADMIN" }
```

**Cadastrar Conta Cliente Demo:**
```powershell
$body = @{
    login = "654321"
    password = "SUA_SENHA"
    server = "Exness-MT5Trial"
    name = "client-demo-v3"
    type = "CLIENT"
} | ConvertTo-Json

curl -Method Post -Uri "http://localhost:8003/api/v1/admin/metaapi/accounts" -Body $body -ContentType "application/json" -Headers @{ "Authorization" = "Bearer SEU_TOKEN_ADMIN" }
```

#### 4. Workflow no Painel Admin
1. Vá em **Admin > MetaApi V3**.
2. Clique em **Add MT5 Account** para a Master e a Cliente.
3. Aguarde o status mudar para **CONNECTED**.
4. Na Master, clique no ícone de escudo (**Shield**) para criar o **CopyFactory Provider**.
5. No backend (futuro), as subscriptions serão automáticas ou via endpoint `/subscriptions`.

---
*Atenção: A V1 permanece operando em paralelo no banco Postgres original.*
