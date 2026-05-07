# CopyTrade Pro Bridge Executor

Executor independente para Windows VPS que consome ordens do Redis publicadas pelo
**Bridge Backend** do CopyTrade Pro, executa no MetaTrader 5 das contas clientes
e devolve o resultado.

> Este projeto é **independente** do CopyTrade Pro principal. Ele pode ser
> testado isoladamente antes de qualquer integração de produção.

## Arquitetura

```
[Bridge Backend]
        │ RPUSH bridge:execute:{client_login}
        ▼
[Redis] ──► [Execution Worker] ──► [MT5 Terminal] ──► resultado
                                          │
                                          ▼
                                  RPUSH bridge:results

[Bridge Auditor] ─► bridge:audit:check:{client_login}
                                          │
                                          ▼
                            [Audit Worker] ─► bridge:audit:results
```

## Requisitos

- Windows 10/11 ou Windows Server (VPS)
- Python 3.12 (64 bits)
- MetaTrader 5 instalado
- Redis acessível (mesmo Redis usado pelo Bridge Backend)

## Instalação no Windows VPS

```powershell
# 1. clonar este projeto
git clone <repo> copytrade-bridge-executor
cd copytrade-bridge-executor

# 2. instalar
./scripts/install_windows.ps1

# 3. configurar
notepad .env
```

## Configuração (.env)

Veja `.env.example`. Variáveis principais:

| Variável | Descrição |
|---|---|
| `REDIS_URL` | URL do Redis (mesmo do Bridge Backend) |
| `EXECUTOR_ID` | Identificador único do VPS |
| `EXECUTOR_MODE` | `test` ou `prod` |
| `MT5_TERMINAL_PATH` | Caminho do `terminal64.exe` |
| `QUEUE_PREFIX` | Prefixo das filas, default `bridge:execute` |
| `RESULT_QUEUE` | Fila de resultados, default `bridge:results` |
| `AUDIT_QUEUE` | Fila de resultados de auditoria |
| `MAX_WORKERS` | Concorrência por processo |
| `ORDER_MAGIC` | Magic number das ordens |
| `ORDER_COMMENT_PREFIX` | Prefixo dos comments (default `CTP`) |
| `DEFAULT_DEVIATION` | Slippage máximo em pontos |
| `ENABLE_REAL_TRADING` | `false` = simulação, `true` = ordens reais |
| `ENABLE_AUDITOR` | Liga o worker auditor |
| `LOG_LEVEL` | `DEBUG` / `INFO` / `WARNING` |

## Executar

```powershell
# modo simulação (default — seguro)
./scripts/run_executor.ps1

# modo real
$env:ENABLE_REAL_TRADING="true"
./scripts/run_executor.ps1
```

## Modo simulação

Quando `ENABLE_REAL_TRADING=false`, o executor **não envia ordens** ao MT5.
Ele apenas valida o payload, resolve o símbolo, normaliza o lote e publica
um resultado `status=simulated` em `bridge:results`. Use sempre este modo
para testar a integração antes de habilitar trading real.

## Teste manual sem CopyTrade Pro

Publique uma ordem fake no Redis e veja o executor consumindo:

```powershell
python scripts/test_order.py --login 123456 --symbol XAUUSD --type BUY --lot 0.01
```

## Health check

Quando `HEALTH_API_ENABLED=true` (default), expõe FastAPI em
`http://127.0.0.1:8765`:

- `GET /health` — status geral
- `GET /status` — métricas internas (ordens recebidas, executadas, falhas)
- `GET /accounts` — sessões MT5 ativas
- `GET /queues` — filas escutadas e tamanho atual

## Logs

```
logs/executor.log    # geral
logs/orders.log      # cada ordem recebida + resultado
logs/errors.log      # apenas erros
```

## Auditoria local

O `audit_worker` aceita comandos:

- `CHECK_POSITION` — confirma que a posição existe (matched / not_found /
  wrong_direction / wrong_lot)
- `CHECK_CLOSED` — confirma fechamento (matched / still_open)
- `FORCE_CLOSE` — fecha posição **somente** se ela for vinculada ao CopyTrade
  Pro (magic correto **ou** comment com prefixo `CTP:` e o `master_ticket`).

> Nunca fechamos posição manual do cliente.

## Parar o executor

`Ctrl+C` na janela. O processo encerra com graceful shutdown (drena ordens em
voo até `SHUTDOWN_TIMEOUT_SECONDS`).

## Segurança de credenciais

Esta primeira versão aceita `client_password` no payload para facilitar
testes. **Em produção**, troque por:

1. Cofre de credenciais no backend + token temporário, ou
2. Login pré-provisionado no terminal e payload sem senha.

## Próximos passos (não implementados ainda)

- Painel completo
- Billing / usuários
- Integração direta com banco principal
- Criptografia avançada de credenciais
- Alteração no CopyTrade Pro
