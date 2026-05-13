# V2 Real Production Rollout Plan

## Estratégia de Rollout
A migração da V1 para a V2 institucional será gradual e controlada através do campo `executor_version` na tabela `mt5_accounts`.

### Fases do Rollout
1. **Fase 1 (Teste Real Controlado)**:
   - 1 Master Real.
   - 2 Clientes Reais pequenos.
   - Monitoramento intensivo de latência e slippage.
2. **Fase 2 (Escala Inicial)**:
   - 5-10 Clientes.
   - Validação do isolamento de processos (1 MT5 por conta).
3. **Fase 3 (Expansão)**:
   - 50+ Clientes.
   - Ativação do `AUTO_REMOVE_DISCONNECTED_ACCOUNTS` após estabilidade provada.
4. **Fase 4 (Full Production)**:
   - Migração total das contas compatíveis com o modelo institucional.

## Segurança e Isolamento
- **VPS Isolado**: A V2 roda em um novo Windows VPS institucional, totalmente separado da infraestrutura da V1.
- **Distributed Lock**: Implementado via Redis (DB 2) para garantir que uma conta NUNCA seja executada por dois VPS ao mesmo tempo.
- **Routing**: O Ubuntu roteia as ordens baseando-se no `executor_version`. VPS Institucional processa apenas `executor_version='v2'`.

## Monitoramento e Métricas Críticas
- **Latência de Execução**: Tempo entre o sinal do Master e a execução no Cliente.
- **Slippage**: Diferença de preço entre Master e Cliente.
- **Uso de Recursos**: CPU e RAM por processo MT5.
- **Stability Score**: Frequência de reconexões e erros críticos.

## Comandos Administrativos
### Rollback para V1
Caso seja detectada instabilidade na V2 para uma conta específica, use o comando:
```bash
python -m backend.agent_v2.scripts.migrate_account --account_id <UUID> --to v1
```
Isso alterará o `executor_version` para `v1`, e o VPS antigo assumirá a execução na próxima ordem.

### Shadow Mode
Para testar a infraestrutura sem executar ordens reais:
Defina `V2_SHADOW_MODE=true` no `.env` do VPS V2. O sistema processará tudo (alocação, locks, roteamento) mas não enviará a ordem ao MT5.

## Limites Operacionais Recomendados
- **Contas por VPS**: Inicialmente limitado a 50 processos MT5.
- **RAM Mínima**: 16GB para 50 contas (estimado 200-300MB por terminal MT5 em background).
