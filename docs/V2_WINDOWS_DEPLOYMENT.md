# CopyTrade Pro V2 — Windows Deployment Guide

Este guia detalha como instalar a infraestrutura do **CopyTrade Pro V2** em um Windows VPS novo, garantindo isolamento total da V1 e segurança na transição para operações reais.

## 1. Requisitos do Servidor
*   **SO:** Windows Server 2019 ou 2022 (preferencial).
*   **Hardware:** Mínimo 2 vCPU, 4GB RAM (Recomendado 4 vCPU, 8GB+ para múltiplos terminais).
*   **Conectividade:** Latência baixa com o broker Exness (VPS em Londres ou Amsterdã recomendado).

## 2. Instalação do Python 3.12
1.  Baixe o instalador do [Python 3.12.x](https://www.python.org/downloads/windows/).
2.  **IMPORTANTE:** Marque a opção **"Add Python to PATH"** durante a instalação.
3.  Abra o PowerShell e verifique: `python --version`.

## 3. Instalação do Git
1.  Baixe o [Git for Windows](https://git-scm.com/download/win).
2.  Siga o instalador padrão.
3.  Verifique: `git --version`.

## 4. Instalação do MetaTrader 5 Exness
1.  Baixe o instalador oficial da Exness.
2.  Instale no caminho padrão: `C:\Program Files\MetaTrader 5`.
3.  Abra o terminal manualmente uma vez para aceitar os termos e baixar os assets iniciais.

## 5. Clonar o Repositório
No PowerShell:
```powershell
cd C:\
git clone <seu-repo-url> copytrade_app
cd copytrade_app
```

## 6. Criar Ambiente Virtual (venv)
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

## 7. Instalar Dependências
```powershell
pip install -r backend/requirements.txt
```

## 8. Configurar .env da V2
1.  Copie o exemplo: `cp backend/agent_v2/.env.example backend/agent_v2/.env`.
2.  Edite o arquivo `backend/agent_v2/.env` com as seguintes chaves críticas:
    *   `V2_DATABASE_URL_SYNC`: URL do seu PostgreSQL.
    *   `V2_REDIS_URL`: URL do seu Redis (use DB `/2`).
    *   `V2_EXECUTION_MODE=DRY_RUN` (mantenha assim inicialmente).
    *   `V2_ORDER_EXECUTION_ENABLED=false`.

## 9. Criar Pastas de Isolamento
No PowerShell (como Administrador):
```powershell
mkdir C:\copytrade_v2
mkdir C:\MT5_Masters_V2
mkdir C:\MT5_Pool_V2
mkdir C:\copytrade_v2_logs
```

## 10. Aplicar Migrations (015 e 016)
As migrations de V2 criam as tabelas de flags e controle de troca de estratégia.
```powershell
alembic upgrade head
```

## 11. Rodar Smoke Tests
Verifique se os componentes internos estão saudáveis:
```powershell
# Dentro da venv
$env:PYTHONPATH="."
python backend/agent_v2/scripts/smoke_safety_guard.py
python backend/agent_v2/scripts/smoke_executor.py
python backend/agent_v2/scripts/smoke_close_reconciler.py
python backend/agent_v2/scripts/smoke_wiring_distributor.py
```

## 12. Iniciar em DRY_RUN
Rode o processo principal para ver se ele conecta ao Redis e monitora as filas sem executar ordens reais:
```powershell
python backend/agent_v2/main.py
```

## 13. Configurar Master Demo
No banco de dados, marque uma master existente (ou crie uma) para usar a V2:
```sql
INSERT INTO v2_master_flags (master_id, engine_version, is_active) 
VALUES ('uuid-da-master', 'v2', true);
```

## 14. Configurar Cliente Demo
No banco de dados, habilite um cliente para a V2:
```sql
INSERT INTO v2_account_flags (account_id, engine_version, can_execute) 
VALUES ('uuid-da-conta', 'v2', true);
```

## 15. Ativar DEMO_ONLY com Whitelist
No seu `.env`:
1.  Mude `V2_EXECUTION_MODE=DEMO_ONLY`.
2.  Mude `V2_ORDER_EXECUTION_ENABLED=true`.
3.  Adicione o Login ou UUID na whitelist: `V2_DEMO_WHITELIST_ACCOUNTS=123456,789012`.
4.  Reinicie o processo.

## 16. Testar Abertura e Fechamento
Abra uma ordem na Master Demo. Verifique os logs em `C:\copytrade_v2_logs` para confirmar que a ordem foi replicada no terminal do pool.

## 17. Ativar CloseReconciler
No `.env`, garanta que:
`V2_CLOSE_RECONCILER_ENABLED=true`
Isso garante que se um fechamento falhar por timeout do broker, o sistema tentará novamente até confirmar o fechamento.

## 18. Instalar Serviço Windows CopyTradeProV2
Para rodar 24/7 sem janelas abertas:
1.  Edite `backend/agent_v2/scripts/install_windows_service.ps1` com os caminhos corretos.
2.  Execute no PowerShell como Admin:
```powershell
.\backend\agent_v2\scripts\install_windows_service.ps1
```

## 19. Comandos de Operação
*   **Iniciar:** `Start-Service CopyTradeProV2`
*   **Parar:** `Stop-Service CopyTradeProV2`
*   **Status:** `Get-Service CopyTradeProV2`

## 20. Troubleshooting Comum
*   **Terminal não abre:** Verifique se o `V2_MT5_TERMINAL_PATH` no `.env` está correto e se o usuário tem permissão.
*   **Erro de Login:** Verifique se as credenciais no cofre estão corretas. O log mostrará `AUTH_FAILED`.
*   **Circuit Breaker Aberto:** O pool parou após 5 falhas seguidas. Verifique a conexão com o broker e resete via Redis (ver Runbook).

## 21. Rollback Seguro
Para voltar um cliente para a V1:
1.  Pare o serviço V2 ou remova o cliente da whitelist V2.
2.  No banco, mude `engine_version` para 'v1' na tabela `v2_account_flags`.
3.  Certifique-se de que não há ordens abertas durante a transição (ou use o Safe Drain).
