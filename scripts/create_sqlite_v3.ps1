# Script para criar tabelas V3 no SQLite via SQLAlchemy (Inicialização rápida)
# Use este script se preferir não usar Alembic inicialmente

$env:DATABASE_URL = "sqlite+aiosqlite:///./copytrade_v3.db"
$env:ENVIRONMENT = "homologation"

Write-Host "Iniciando criação das tabelas no SQLite..." -ForegroundColor Cyan

python -c @"
import asyncio
from app.core.database import engine, Base
from app.models import *

async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print('Tabelas criadas com sucesso!')

if __name__ == '__main__':
    asyncio.run(create_tables())
"@

Write-Host "Processo concluído." -ForegroundColor Green
