# Script para criar tabelas V3 no SQLite via SQLAlchemy (Inicialização rápida)
# Executar dentro da pasta 'backend'

$env:DATABASE_URL = "sqlite+aiosqlite:///./copytrade_v3.db"
$env:ENVIRONMENT = "homologation"
$env:PYTHONPATH = "."

Write-Host "Iniciando criação das tabelas no SQLite (copytrade_v3.db)..." -ForegroundColor Cyan

python -c @"
import asyncio
import sys
import os
sys.path.append(os.getcwd())

from app.core.database import engine, Base
# Importar modelos para garantir que o Base.metadata esteja populado
try:
    from app.models import user, account, signal, trade # Ajuste conforme seus modelos
except ImportError:
    # Se não conseguir importar específicos, tenta o init do models
    try:
        from app.models import Base as ModelsBase
    except ImportError:
        pass

async def create_tables():
    async with engine.begin() as conn:
        # Importar modelos aqui dentro também para garantir
        import app.models
        await conn.run_sync(Base.metadata.create_all)
    print('Tabelas criadas com sucesso no arquivo copytrade_v3.db!')

if __name__ == '__main__':
    asyncio.run(create_tables())
"@

Write-Host "Processo concluído." -ForegroundColor Green
