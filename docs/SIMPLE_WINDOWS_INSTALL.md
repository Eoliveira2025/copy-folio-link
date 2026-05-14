# CopyTrade Pro V2 Institutional - Simple Windows Installation

Este guia explica como instalar o **CopyTrade Pro V2** no seu novo Windows VPS institucional de forma isolada e segura.

## Pré-requisitos

1.  **Windows VPS**: Windows Server 2019 ou superior recomendado.
2.  **Python 3.12**: Baixe em [python.org](https://www.python.org/downloads/) e marque "Add Python to PATH" durante a instalação.
3.  **MetaTrader 5**: Instalado no caminho padrão (`C:\Program Files\MetaTrader 5`).
4.  **Acesso Admin**: PowerShell deve ser executado como Administrador.

## Passo a Passo

### 1. Extração
1.  Baixe o arquivo `copytrade-v2-deploy-fixed.zip`.
2.  Extraia o conteúdo diretamente para a raiz do seu drive `C:`.
3.  A estrutura final deve ser: `C:\copytrade-v2`.

### 2. Instalação Automatizada
1.  Clique com o botão direito no botão Iniciar e selecione **Terminal (Admin)** ou **Windows PowerShell (Admin)**.
2.  Navegue até a pasta:
    ```powershell
    cd C:\copytrade-v2
    ```
3.  Execute o script de instalação:
    ```powershell
    .\scripts\install_v2_windows_vps.ps1
    ```
    *O script criará o ambiente virtual (venv), instalará as dependências e preparará as pastas isoladas.*

### 3. Configuração
1.  Abra o arquivo `C:\copytrade-v2\.env` com o Bloco de Notas ou VS Code.
2.  Configure as variáveis essenciais:
    *   `V2_DATABASE_URL_SYNC`: URL do banco PostgreSQL.
    *   `V2_REDIS_URL`: URL do Redis (usando DB /2 para isolamento).
    *   `V2_MT5_CREDENTIAL_KEY`: Sua chave de criptografia de 32 bytes.
    *   `V2_EXECUTION_MODE`: Mude para `LIVE` quando estiver pronto.

### 4. Teste de Conectividade (Pre-flight)
Antes de iniciar, valide se tudo está configurado corretamente:
```powershell
.\venv\Scripts\python.exe backend\agent_v2\tests\run_final_v2_preflight.py
```

### 5. Iniciar Operação
Para iniciar o executor Master da V2:
```powershell
.\scripts\start_v2_executor.ps1
```

## Scripts de Operação (C:\copytrade-v2\scripts)

*   `start_v2_executor.ps1`: Inicia o sistema V2.
*   `stop_v2_executor_safe.ps1`: Para a V2 de forma segura (não afeta a V1).
*   `health_check_v2.ps1`: Verifica se os processos e conexões estão ativos.
*   `open_vps_monitor.ps1`: Abre o dashboard local no navegador.

---
*Suporte: CopyTrade Pro Institutional Team*
