# CopyTrade Pro — Windows VPS Agent Setup

## Requisitos
- Windows Server 2022
- Python 3.12+
- MetaTrader 5 instalado (terminal64.exe)
- Acesso de rede ao Ubuntu server (PostgreSQL porta 5432, Redis porta 6379)

## Instalação

```powershell
# 1. Clonar/copiar a pasta backend para o Windows VPS
# 2. Instalar dependências
cd backend
pip install -r requirements-agent.txt

# 3. Configurar ambiente
copy agent\.env.example agent\.env
# Editar agent\.env com suas credenciais
```

## Configuração (.env)

```env
DATABASE_URL_SYNC=postgresql://postgres:SUA_SENHA@91.98.20.163:5432/copytrade
REDIS_URL=redis://:REDIS_PASSWORD@91.98.20.163:6379/0
MT5_CREDENTIAL_KEY=mesma-chave-do-servidor-ubuntu
MT5_TERMINAL_PATH=C:\Program Files\MetaTrader 5\terminal64.exe
```

**IMPORTANTE**: O `MT5_CREDENTIAL_KEY` deve ser EXATAMENTE o mesmo usado no backend Ubuntu.

## Executar

```powershell
cd backend
python -m agent.main
```

## Regras de Cópia

| Estratégia    | Tipo de Cópia | Fórmula |
|---------------|---------------|---------|
| low           | Exata 1:1     | volume = master_volume |
| medium        | Exata 1:1     | volume = master_volume |
| high          | Exata 1:1     | volume = master_volume |
| pro           | Exata 1:1     | volume = master_volume |
| expert        | Exata 1:1     | volume = master_volume |
| expert_pro    | Proporcional  | volume = (client_balance / master_balance) × master_volume × risk_multiplier |

## Arquitetura

```
Windows VPS
  │
  ├── Master Monitor (1 subprocess por conta master)
  │   └── Poll MT5 positions a cada 50ms
  │   └── Publica eventos no Redis
  │
  ├── Trade Distributor (thread pool)
  │   └── Consome eventos do Redis
  │   └── Calcula lotes (1:1 ou proporcional)
  │   └── Enfileira ordens por cliente
  │
  ├── Execution Workers (1 subprocess por conta cliente)
  │   └── Desenfileira ordens do Redis
  │   └── Executa no MT5 com controle de slippage
  │   └── Retry com backoff exponencial
  │   └── Dead letter queue para falhas
  │
  ├── Result Tracker (thread)
  │   └── Persiste resultados no PostgreSQL
  │
  └── DB Synchronizer (thread, a cada 30s)
      └── Detecta novas contas master/cliente
      └── Spawna/para processos automaticamente
      └── Sincroniza balances
```

## Monitoramento

O agent loga status a cada 15 segundos:
```
Agent status: 3/3 masters, 150/150 clients
```

Logs detalhados em `agent.log`.

## Segurança

- Senhas MT5 são armazenadas criptografadas (Fernet AES-128)
- Comunicação com PostgreSQL deve usar SSL em produção
- Comunicação com Redis deve usar senha + TLS
- Firewall: abrir apenas portas 5432 (PostgreSQL) e 6379 (Redis) do Ubuntu

## Capacidade

- Cada subprocess MT5 consome ~50-100MB RAM
- Para 2000 contas: ~200GB RAM (dividir entre múltiplos VPS)
- Recomendado: 1 VPS com 16GB para ~150 contas simultâneas
- Escalar horizontalmente adicionando mais VPS com o mesmo agent
