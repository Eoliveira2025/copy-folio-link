# Bridge Architecture

## Visão geral

A camada **Bridge** reduz o consumo de memória do antigo modelo (um terminal MT5
por master para polling de posições) substituindo o monitoramento por um EA
MQL5 que envia eventos diretamente para a API.

```
[Master MT5 + EA]  ──HTTPS──▶  [FastAPI /bridge/signal]
                                       │
                                  persiste em
                                bridge_signals
                                       │
                              Redis pub/sub:
                              bridge:signal:{master_id}
                                       │
                          [Bridge Distributor worker]
                                       │
              calcula lote proporcional por cliente,
              persiste bridge_execution_orders e
              enfileira em Redis list:
              bridge:execute:{client_login}
                                       │
                          [Windows VPS Executor]
                                       │
                            executa nas contas MT5 dos clientes
```

A nova camada roda **em paralelo** ao copy atual e está protegida por
`BRIDGE_ENABLED`. Nada do fluxo antigo é alterado.

## Componentes

| Caminho | Responsabilidade |
|---|---|
| `backend/app/api/routes/bridge.py` | Endpoint `POST /api/v1/bridge/signal` |
| `backend/app/core/bridge_security.py` | Valida `Authorization: Bearer BRIDGE_TOKEN` |
| `backend/app/core/bridge_config.py` | Settings + feature flag |
| `backend/app/schemas/bridge.py` | Validação de payload |
| `backend/app/models/bridge.py` | `BridgeSignal`, `BridgeExecutionOrder` |
| `backend/app/services/bridge_service.py` | Persistência + publish Redis |
| `backend/app/workers/bridge_distributor.py` | Worker async (pub/sub → fila por cliente) |
| `mql5/CopyTradeProBridge/CopyTradeProBridge.mq5` | EA na master |

## Ativação

1. Copiar variáveis do `backend/.env.bridge.example` para o `.env` real e
   ajustar:
   ```
   BRIDGE_ENABLED=true
   BRIDGE_TOKEN=<token-secreto-forte>
   ```
2. Rodar a migration:
   ```
   cd backend && alembic upgrade head
   ```
3. Subir o worker (processo separado):
   ```
   python -m app.workers.bridge_distributor
   ```
4. Compilar o EA `CopyTradeProBridge.mq5` no MT5 da master, configurar
   `API_URL`, `API_TOKEN`, `MASTER_ID` e liberar a URL em
   `Tools > Options > Expert Advisors > Allow WebRequest for listed URL`.

## Endpoint

`POST /api/v1/bridge/signal`

Header: `Authorization: Bearer <BRIDGE_TOKEN>`

Body:
```json
{
  "master_id": "low-master-01",
  "strategy_id": "uuid-opcional",
  "action": "OPEN",
  "symbol": "XAUUSD",
  "order_type": "BUY",
  "volume": 1.0,
  "price": 2650.50,
  "sl": 2640.00,
  "tp": 2670.00,
  "master_ticket": "123456",
  "position_id": "123456",
  "master_balance": 10000
}
```

Erros:
- `503` se `BRIDGE_ENABLED=false`
- `403` se token inválido
- `422` se payload inválido (volume, símbolo, action)

## Cálculo de lote

```
client_lot = master_volume * (client_balance / master_balance) * risk_multiplier
```
Normalizado por `BRIDGE_MIN_LOT`, `BRIDGE_MAX_LOT`, `BRIDGE_DEFAULT_LOT_STEP`.
Lote final < min → `skipped_lot_too_small`.

## Filtros de cliente

O distributor só enfileira ordens para clientes cujas contas:
- estão `MT5Status.CONNECTED`
- assinatura `TRIAL` ou `ACTIVE` (se `BRIDGE_REQUIRE_ACTIVE_SUBSCRIPTION=true`)
- `access_status != blocked`
- `UserStrategy.is_active = true` para a estratégia em questão

## Idempotência

`UNIQUE (bridge_signal_id, mt5_account_id, action)` impede ordens duplicadas
para o mesmo sinal.

## Contrato da fila Windows Executor

`bridge:execute:{client_login}` (Redis LIST, RPUSH/BLPOP):

```json
{
  "execution_order_id": "uuid",
  "client_login": "123456",
  "mt5_account_id": "uuid",
  "action": "OPEN",
  "symbol": "XAUUSD",
  "order_type": "BUY",
  "lot": 0.02,
  "price": 2650.50,
  "sl": 2640.00,
  "tp": 2670.00,
  "master_ticket": "123456",
  "strategy_id": "uuid"
}
```

## Migração gradual

1. Manter sistema atual em produção.
2. Habilitar Bridge em conta demo: `BRIDGE_ENABLED=true` apenas em ambiente de
   testes.
3. Comparar ordens geradas pelo Bridge com as do copy antigo no painel
   Admin > Bridge.
4. Subir o Windows Executor consumidor das filas.
5. Migrar masters um a um.

## Rollback

Setar `BRIDGE_ENABLED=false` e parar o worker `bridge_distributor`. O sistema
antigo continua intocado.
