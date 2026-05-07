# CopyTradeProBridge EA

EA MQL5 instalado **somente na conta MASTER**. Ele detecta eventos OPEN / CLOSE /
MODIFY (SL/TP/volume) e envia via `WebRequest` HTTPS para o endpoint
`POST /api/v1/bridge/signal` da API CopyTrade Pro.

## Configuração

1. Copie `CopyTradeProBridge.mq5` para `MQL5/Experts/` do terminal MASTER e
   compile no MetaEditor.
2. Anexe o EA a um gráfico — qualquer símbolo serve, ele monitora todas as
   posições da conta.
3. Configure as inputs:
   - `API_URL` — ex.: `https://api.seu-dominio.com/api/v1/bridge/signal`
   - `API_TOKEN` — mesmo valor de `BRIDGE_TOKEN` no backend
   - `MASTER_ID` — identificador único do master (ex.: `low-master-01`)
   - `STRATEGY_ID` — UUID da estratégia (opcional, pode resolver pelo `MASTER_ID`)
   - `TIMER_MS` — intervalo de varredura, padrão `250`
   - `SEND_BALANCE` — envia o saldo da master para cálculo proporcional

## IMPORTANTE — Liberar URL no MT5

Para o `WebRequest` funcionar, o usuário precisa liberar a URL da API:

`Tools > Options > Expert Advisors > Allow WebRequest for listed URL`

E adicionar a URL base (ex.: `https://api.seu-dominio.com`).

## Logs

Os eventos aparecem na aba **Experts** do MT5:

- `[Bridge] OPEN XAUUSD vol=1.00 http=200`
- `[Bridge] WebRequest error 4060` → URL não liberada
- `[Bridge] API_TOKEN missing` → input vazio
