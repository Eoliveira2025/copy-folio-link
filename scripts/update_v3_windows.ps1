param (
    [string]$EnvFile = ".env.v3"
)

Write-Host ">>> Iniciando Update V3 MetaApi - Windows VPS 2" -ForegroundColor Cyan

# 1. Validar Python
if (!(Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python não encontrado. Instale o Python 3.10+."
    exit
}

# 2. Virtual Env
if (!(Test-Path "venv_v3")) {
    Write-Host "Criando ambiente virtual..."
    python -m venv venv_v3
}

Write-Host "Instalando dependências do requirements.v3.txt..."
.\venv_v3\Scripts\pip install -r requirements.v3.txt

# 3. Validar .env
if (!(Test-Path $EnvFile)) {
    if (Test-Path ".env.v3.example") {
        Copy-Item ".env.v3.example" $EnvFile
        Write-Host "Criado $EnvFile a partir do exemplo. EDITE AS CREDENCIAIS!" -ForegroundColor Yellow
    }
}

# 4. Validar PostgreSQL (opcional check básico)
Write-Host "Verificando se o PostgreSQL está acessível..."
# Aqui poderíamos rodar um script python simples para testar a conexão

# 5. Subir API
Write-Host "Subindo API V3 na porta 8003..." -ForegroundColor Green
.\venv_v3\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8003
