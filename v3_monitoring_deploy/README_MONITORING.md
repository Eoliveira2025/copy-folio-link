# V3 Monitoring Deploy Package

Este pacote contém os arquivos necessários para implantar o monitoramento institucional da V3 MetaApi.

## Arquivos Incluídos:
- Backend: Models, Routes, Services e Worker.
- Frontend: Hooks, API Client e Painel Admin atualizado.
- Scripts: Script de deploy e worker isolado.

## Instruções de Implantação no Ubuntu:
1. Copie o conteúdo da pasta 'backend' para /opt/copytrade/backend/
2. Execute o script de deploy:
   cd /opt/copytrade/backend && bash scripts/deploy_v3_monitoring.sh
3. Verifique o status do serviço:
   sudo systemctl status copytrade-v3-monitor

## Requisitos:
- V3_COPY_ENABLED=true no .env
- MetaApi Service rodando (para as rotas de importação)
