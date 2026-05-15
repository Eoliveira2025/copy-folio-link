# Script para rodar Migrations Alembic no SQLite
# Executar dentro da pasta 'backend'

$env:DATABASE_URL = "sqlite+aiosqlite:///./copytrade_v3.db"
$env:DATABASE_URL_SYNC = "sqlite:///./copytrade_v3.db"
$env:ENVIRONMENT = "homologation"
$env:PYTHONPATH = "."

Write-Host "Rodando migrations Alembic no SQLite..." -ForegroundColor Cyan

alembic upgrade head

Write-Host "Migrations aplicadas com sucesso." -ForegroundColor Green
