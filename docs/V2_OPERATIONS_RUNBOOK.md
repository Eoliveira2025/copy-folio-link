# CopyTrade Pro V2 — Operations Runbook

Este documento é destinado a operadores do sistema para gestão do dia a dia da infraestrutura V2.

## Gestão de Masters e Clientes

### Como adicionar nova Master à V2
1.  Identifique o `master_id` (UUID) no banco.
2.  Insira ou atualize na tabela `v2_master_flags`:
    ```sql
    INSERT INTO v2_master_flags (master_id, engine_version, is_active) 
    VALUES ('UUID', 'v2', true)
    ON CONFLICT (master_id) DO UPDATE SET engine_version = 'v2', is_active = true;
    ```

### Como adicionar Cliente em V2
1.  Garanta que a conta não possui posições abertas na V1.
2.  Insira na tabela `v2_account_flags`:
    ```sql
    INSERT INTO v2_account_flags (account_id, engine_version, can_execute) 
    VALUES ('UUID', 'v2', true);
    ```
3.  Se estiver em `DEMO_ONLY`, adicione o Login/UUID no `.env` em `V2_DEMO_WHITELIST_ACCOUNTS`.

## Monitoramento

### Como ver Pools ativos
Os pools são registrados no Redis sob a chave `copytrade_v2:pools:active`.
Via CLI: `redis-cli -n 2 HGETALL copytrade_v2:pools:active`

### Como ver a Fila de Execução
Cada terminal/pool tem sua própria fila no Redis:
`redis-cli -n 2 LLEN copytrade_v2:queue:pool_<id>`

### Como ver Saúde dos Pools (Heartbeat)
O sistema publica o estado de saúde a cada 15 segundos:
`redis-cli -n 2 HGETALL copytrade_v2:health:pool_<id>`
Verifique: `circuit_breaker_status`, `is_alive`, `queue_depth`.

## Troca de Estratégia (Migration)

### Modo SAFE_DRAIN (Recomendado)
Aguardar todas as posições fecharem antes de mudar de pool/estratégia.
1.  Crie o request:
    ```sql
    INSERT INTO v2_strategy_change_requests (account_id, target_strategy_id, mode, status)
    VALUES ('ACCOUNT_UUID', 'STRATEGY_UUID', 'SAFE_DRAIN', 'PENDING');
    ```
2.  O sistema moverá a conta para `EXIT_ONLY`. Novas ordens são ignoradas, apenas fechamentos são processados. Quando zerar, a conta é movida para o novo pool.

### Modo FORCE_CLOSE_AND_SWITCH
Fecha tudo imediatamente e troca.
1.  Crie o request com `mode = 'FORCE_CLOSE_AND_SWITCH'`.
2.  Requer que `requires_admin_approval` seja falso ou aprovado.

## Segurança e Whitelist Real

### Ativar LIVE_WHITELIST para 1 conta real
1.  No `.env`, altere `V2_EXECUTION_MODE=LIVE_WHITELIST`.
2.  Adicione o login real em `V2_LIVE_WHITELIST_ACCOUNTS=987654321`.
3.  Reinicie o serviço. **Atenção:** Apenas as contas nesta lista executarão ordens reais.

### Como voltar conta para V1
1.  Certifique-se de que a conta está sem ordens (ou use `SAFE_DRAIN`).
2.  Mude `engine_version = 'v1'` na tabela `v2_account_flags`.

## Resolução de Problemas

### Como Pausar um Pool
Para manutenção emergencial de um terminal:
`redis-cli -n 2 HSET copytrade_v2:health:pool_<id> status PAUSED`

### Como Resetar Circuit Breaker
Se o pool entrou em estado `OPEN` (bloqueado) após falhas:
`redis-cli -n 2 HDEL copytrade_v2:health:pool_<id> circuit_breaker_failures`
O sistema tentará a próxima ordem e, se tiver sucesso, resetará o status.

### Como lidar com CLOSE que não fechou
1.  O `CloseReconciler` tentará por padrão 5 vezes (configurável no `.env`).
2.  Verifique nos logs o `retcode`.
3.  Se o erro persistir (ex: `MARKET_CLOSED`), o reconciler tentará novamente assim que o mercado abrir ou até atingir o limite.
4.  Se precisar intervir manualmente, feche no MT5. O reconciler detectará o fechamento manual e marcará como `JA_NAO_EXISTE`.
