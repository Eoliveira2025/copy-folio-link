# V2 Institutional Sandbox Validation Checklist

Este documento descreve os passos para validar a arquitetura V2 no Windows VPS de forma segura.

## 1. Preparação do Ambiente

- [ ] Criar diretório `C:\MT5_Pool_V2_Sandbox`
- [ ] Criar diretório `C:\MT5_Pool_V2_Sandbox\logs`
- [ ] Criar diretório `C:\MT5_Pool_V2_Sandbox\instances`
- [ ] Verificar se o Python 3.12 está no PATH
- [ ] Verificar se o `terminal64.exe` está em `C:\Program Files\MetaTrader 5` ou local equivalente

## 2. Configuração do Sandbox (`.env.v2.sandbox`)

Crie um arquivo `.env.v2.sandbox` com:
```env
V2_MT5_POOL_V2_ENABLED=true
V2_SESSION_DRY_RUN=true
V2_EXECUTION_MODE=DRY_RUN
V2_V2_POOL_DIR=C:\MT5_Pool_V2_Sandbox\instances
V2_V2_LOGS_DIR=C:\MT5_Pool_V2_Sandbox\logs
V2_REDIS_URL=redis://localhost:6379/2
```

## 3. Execução do Teste

Execute o comando PowerShell abaixo:

```powershell
# Ativar venv
.\venv\Scripts\activate

# Definir variáveis de ambiente temporárias
$env:V2_MT5_POOL_V2_ENABLED="true"
$env:V2_SESSION_DRY_RUN="true"

# Rodar script de sandbox
python backend/agent_v2/tests/run_v2_windows_sandbox.py
```

## 4. Critérios de Sucesso (Checklist)

- [ ] **Isolamento de Processo**: Cada conta (1 Master + 2 Clientes) deve ter seu próprio `terminal64.exe` com PID único.
- [ ] **Consumo de Recursos**: Cada terminal deve consumir entre 100MB-300MB de RAM em standby.
- [ ] **Persistência de Diretório**: Cada instância deve usar sua pasta em `C:\MT5_Pool_V2_Sandbox\instances\{login}`.
- [ ] **Roteamento de Estratégia**: O log deve confirmar que ordens de Master LOW nunca são enviadas para Clientes MEDIUM.
- [ ] **Limpeza**: Ao finalizar o script, todos os processos `terminal64.exe` criados pelo sandbox devem ser encerrados automaticamente.
- [ ] **Proteção de Produção**: Nenhum processo da V1 (pasta original) deve ser afetado ou encerrado.

## 5. Logs

Os logs detalhados estaront disponíveis em:
`C:\MT5_Pool_V2_Sandbox\logs\v2_sandbox_test.log`
