# CopyTrade Pro — Documentação Técnica Completa

> Última atualização: 2026-03-25
> Versão: 1.0.0

---

## Sumário

1. [Visão Geral da Arquitetura](#1-visão-geral-da-arquitetura)
2. [Infraestrutura](#2-infraestrutura)
3. [Backend (FastAPI)](#3-backend-fastapi)
4. [Frontend (React + Vite)](#4-frontend-react--vite)
5. [Agent (Windows VPS)](#5-agent-windows-vps)
6. [MT5 Provisioning](#6-mt5-provisioning)
7. [Billing / Asaas](#7-billing--asaas)
8. [Sistema de Controle de Acesso](#8-sistema-de-controle-de-acesso)
9. [API Completa](#9-api-completa)
10. [Variáveis de Ambiente](#10-variáveis-de-ambiente)
11. [Instalação Completa (Ubuntu)](#11-instalação-completa-ubuntu)
12. [Instalação Windows VPS](#12-instalação-windows-vps)
13. [Restore e Manutenção](#13-restore-e-manutenção)
14. [Troubleshooting](#14-troubleshooting)
15. [Segurança](#15-segurança)
16. [Deploy em Produção](#16-deploy-em-produção)

---

## 1. Visão Geral da Arquitetura

### Diagrama de Alto Nível

```
┌─────────────────────────────────────────────────────────────────┐
│                      UBUNTU SERVER                              │
│                                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │
│  │ Nginx    │  │ FastAPI  │  │ Redis    │  │ PostgreSQL   │   │
│  │ :80/443  │→ │ :8000    │  │ :6379    │  │ :5432        │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────┘   │
│       ↑            ↑ ↓            ↑ ↓                          │
│  ┌──────────┐  ┌──────────┐                                    │
│  │ Frontend │  │ Celery   │                                    │
│  │ (dist/)  │  │ Workers  │                                    │
│  └──────────┘  └──────────┘                                    │
└─────────────────────────┬───────────────────────────────────────┘
                          │ Redis pub/sub + queues
                          ↓
┌─────────────────────────────────────────────────────────────────┐
│                    WINDOWS VPS                                  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────┐      │
│  │                  Agent (Python)                       │      │
│  │                                                       │      │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │      │
│  │  │ Master   │  │ Trade    │  │ Execution        │   │      │
│  │  │ Monitor  │  │ Distrib. │  │ Workers          │   │      │
│  │  │ (1/master│  │ (thread  │  │ (1/client acct)  │   │      │
│  │  │  account)│  │  pool)   │  │                  │   │      │
│  │  └──────────┘  └──────────┘  └──────────────────┘   │      │
│  │       ↓              ↓              ↓                │      │
│  │  ┌──────────────────────────────────────────────┐    │      │
│  │  │          MetaTrader 5 Terminals              │    │      │
│  │  │     (1 instância por conta MT5)              │    │      │
│  │  └──────────────────────────────────────────────┘    │      │
│  └──────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────┘
```

### Fluxo Completo do Sistema

1. **Usuário se cadastra** no frontend → API cria conta + subscription (trial 30 dias)
2. **Usuário conecta conta MT5** → status `PENDING_PROVISION`
3. **Admin revela senha** no painel → faz primeiro login manual no MT5
4. **Admin confirma provisionamento** → status muda para `CONNECTED`
5. **Agent no Windows VPS** detecta conta via Redis → inicia terminal MT5
6. **Master Monitor** detecta trades do master → publica eventos no Redis
7. **Distributor** calcula lotes → enfileira ordens por cliente
8. **Executor** executa ordens no MT5 do cliente com controle de slippage
9. **Billing** gera faturas → Asaas processa pagamento → webhook atualiza status
10. **Access Checker** verifica vencimento → bloqueia/desbloqueia automaticamente

---

## 2. Infraestrutura

### Serviços e Portas

| Serviço      | Container/Processo | Porta  | Descrição                              |
|--------------|-------------------|--------|----------------------------------------|
| Nginx        | host / ct-nginx   | 80/443 | Reverse proxy, serve frontend          |
| FastAPI      | ct-api-new        | 8000   | API REST                               |
| Redis        | ct-redis          | 6379   | Message broker, pub/sub, cache         |
| PostgreSQL   | externo           | 5432   | Banco de dados principal               |
| Celery Worker| ct-celery         | —      | Tarefas assíncronas (billing, access)  |
| Celery Beat  | ct-celery-beat    | —      | Agendamento de tarefas                 |

### Docker

**docker-compose.restore.yml** (produção):
- `ct-redis`: Redis 7 Alpine, sem senha (rede interna)
- `ct-api-new`: FastAPI com Uvicorn, 4 workers
- Rede: `copytrade_net` (bridge)

**Banco de dados**: PostgreSQL 16 externo em `91.98.20.163:5432`
- Database: `copytrade`
- User: `copytrade`
- Extensões requeridas: `uuid-ossp`

### Redis

- Broker do Celery
- Pub/sub para comunicação API ↔ Agent
- Filas de ordens de trade
- Cache de health checks e heartbeats
- Sem persistência obrigatória (appendonly recomendado)

**Canais Redis principais:**
| Canal/Fila                            | Uso                                        |
|---------------------------------------|--------------------------------------------|
| `copytrade:terminal:commands`         | Pub/sub: comandos para o agent (spawn/stop)|
| `copytrade:terminal:queue`            | Lista: fila durável de comandos            |
| `copytrade:engine:commands`           | Pub/sub: comandos para copy engine         |
| `copytrade:engine:queue`              | Lista: fila durável de engine              |
| `copytrade:events:<master_id>`        | Pub/sub: eventos de trade do master        |
| `copytrade:queue:<master_id>`         | Lista: fila de eventos por master          |
| `copytrade:execute:<client_id>`       | Lista: ordens a executar por cliente       |
| `copytrade:results`                   | Pub/sub: resultados de execução            |
| `copytrade:results:<client_id>`       | Lista: histórico de resultados             |
| `copytrade:dead_letter`               | Lista: ordens que falharam (DLQ)           |
| `copytrade:trading_blocked`           | Flag: emergência, bloqueia todo trading    |
| `copytrade:master_balance:<id>`       | String: balanço do master (TTL 120s)       |
| `copytrade:health:heartbeat:<id>`     | String: heartbeat do processo (TTL 60s)    |

---

## 3. Backend (FastAPI)

### Estrutura de Pastas

```
backend/
├── app/
│   ├── main.py                    # Entrypoint FastAPI
│   ├── api/
│   │   ├── __init__.py            # Router aggregation
│   │   ├── deps.py                # Dependencies (auth, admin check)
│   │   └── routes/
│   │       ├── auth.py            # Autenticação
│   │       ├── mt5.py             # Conexão MT5
│   │       ├── strategies.py      # Estratégias
│   │       ├── billing.py         # Billing + webhooks
│   │       ├── admin.py           # Admin panel (CRUD, users, etc.)
│   │       ├── admin_provision.py # Provisioning MT5
│   │       ├── legal.py           # Termos de uso
│   │       ├── risk.py            # Risk protection
│   │       ├── operations.py      # Operations dashboard
│   │       └── dead_letter.py     # Dead letter queue
│   ├── core/
│   │   ├── config.py              # Settings (pydantic-settings)
│   │   ├── database.py            # SQLAlchemy async engine
│   │   ├── security.py            # Hash, JWT, Fernet encrypt
│   │   └── logging_config.py      # Logging setup
│   ├── models/
│   │   ├── user.py                # User + UserRoleMapping
│   │   ├── mt5_account.py         # MT5Account + MT5Status
│   │   ├── subscription.py        # Subscription + AccessStatus
│   │   ├── plan.py                # Plan
│   │   ├── invoice.py             # Invoice + Payment
│   │   ├── strategy.py            # Strategy + MasterAccount + UserStrategy
│   │   ├── strategy_request.py    # StrategyRequest
│   │   ├── upgrade_request.py     # UpgradeRequest
│   │   ├── trade.py               # TradeEvent + TradeCopy
│   │   ├── risk.py                # SystemSettings + RiskIncident
│   │   ├── terms.py               # TermsDocument + TermsAcceptance
│   │   ├── password_reset.py      # PasswordResetToken
│   │   └── dead_letter.py         # DeadLetterTrade
│   ├── schemas/                   # Pydantic request/response models
│   ├── services/
│   │   ├── copy_engine.py         # Redis dispatch para agent
│   │   ├── payments.py            # Gateway abstraction (Asaas, Stripe, etc.)
│   │   ├── strategy_switcher.py   # Auto-switch strategy on plan change
│   │   └── partition_manager.py   # Trade table partitioning
│   ├── workers/
│   │   ├── payment_checker.py     # Celery tasks (billing)
│   │   └── access_checker.py      # Access control worker
│   ├── risk_engine/               # Global equity guard
│   └── middleware/
│       └── rate_limit.py          # Login rate limiting
├── alembic/                       # Database migrations
├── Dockerfile                     # Build do container API
└── requirements.txt               # Dependências Python
```

### Models (Banco de Dados)

#### User (`users`)
| Campo            | Tipo       | Descrição                  |
|------------------|-----------|----------------------------|
| id               | UUID (PK) | Identificador único        |
| email            | String    | Email (unique, indexed)    |
| hashed_password  | String    | Senha bcrypt               |
| full_name        | String    | Nome completo              |
| is_active        | Boolean   | Conta ativa                |
| created_at       | DateTime  | Data de criação            |

#### UserRoleMapping (`user_roles`)
| Campo   | Tipo       | Descrição                |
|---------|-----------|--------------------------|
| id      | UUID (PK) | ID                       |
| user_id | UUID (FK) | → users.id               |
| role    | Enum      | `user` ou `admin`        |

> ⚠️ Roles em tabela separada por segurança (previne privilege escalation).

#### MT5Account (`mt5_accounts`)
| Campo              | Tipo       | Descrição                          |
|--------------------|-----------|-------------------------------------|
| id                 | UUID (PK) | ID                                  |
| user_id            | UUID (FK) | → users.id                          |
| login              | Integer   | Login MT5 (unique)                  |
| encrypted_password | String    | Senha Fernet-encrypted              |
| server             | String    | Servidor Exness (ex: Exness-MT5Real6)|
| status             | Enum      | `pending_provision`, `connected`, `disconnected`, `blocked` |
| balance            | Float     | Último balanço sincronizado         |
| equity             | Float     | Última equity sincronizada          |

#### Subscription (`subscriptions`)
| Campo                | Tipo       | Descrição                       |
|----------------------|-----------|----------------------------------|
| id                   | UUID (PK) | ID                               |
| user_id              | UUID (FK) | → users.id                       |
| plan_id              | UUID (FK) | → plans.id                       |
| status               | Enum      | `trial`, `active`, `expired`, `blocked` |
| access_status        | Enum      | `active`, `warning`, `grace`, `blocked` |
| manual_override      | Boolean   | Admin override (ignora cron)     |
| blocked_at           | DateTime  | Data do bloqueio                 |
| trial_start/end      | DateTime  | Período de trial                 |
| current_period_start | DateTime  | Início do período pago           |
| current_period_end   | DateTime  | Fim do período pago              |
| next_billing_date    | DateTime  | Próxima cobrança                 |
| billing_cycle_days   | Integer   | Ciclo (default 30)               |
| auto_renew           | Boolean   | Renovação automática             |

#### Plan (`plans`)
| Campo              | Tipo     | Descrição                              |
|--------------------|---------|----------------------------------------|
| id                 | UUID    | ID                                     |
| name               | String  | Nome do plano                          |
| price              | Float   | Preço                                  |
| currency           | String  | `USD` ou `BRL`                         |
| allowed_strategies | JSON    | Lista de levels permitidos             |
| trial_days         | Integer | Dias de trial                          |
| max_accounts       | Integer | Máx contas MT5                         |
| active             | Boolean | Plano ativo                            |

#### Invoice (`invoices`)
| Campo           | Tipo       | Descrição                    |
|-----------------|-----------|-------------------------------|
| id              | UUID (PK) | ID                            |
| subscription_id | UUID (FK) | → subscriptions.id            |
| amount          | Float     | Valor                         |
| currency        | String    | Moeda                         |
| status          | Enum      | `pending`, `paid`, `overdue`, `cancelled` |
| issue_date      | DateTime  | Data de emissão               |
| due_date        | DateTime  | Data de vencimento            |
| paid_at         | DateTime  | Data de pagamento             |
| external_id     | String    | ID no gateway (Asaas, etc.)   |
| provider        | Enum      | `asaas`, `stripe`, `mercadopago`, `celcoin` |

#### Strategy (`strategies`)
| Campo           | Tipo     | Descrição                        |
|-----------------|---------|-----------------------------------|
| id              | UUID    | ID                                |
| level           | Enum    | `low`, `medium`, `high`, `pro`, `expert`, `expert_pro` |
| name            | String  | Nome da estratégia                |
| description     | String  | Descrição                         |
| risk_multiplier | Float   | Multiplicador de risco            |
| requires_unlock | Boolean | Requer aprovação admin            |
| min_capital     | Numeric | Capital mínimo (USD)              |

#### MasterAccount (`master_accounts`)
| Campo        | Tipo       | Descrição                    |
|--------------|-----------|-------------------------------|
| id           | UUID (PK) | ID                            |
| strategy_id  | UUID (FK) | → strategies.id (unique)      |
| account_name | String    | Nome descritivo               |
| login        | Integer   | Login MT5 do master (unique)  |
| server       | String    | Servidor MT5                  |
| balance      | Float     | Último balanço                |

### Workers (Celery)

**Tarefas agendadas (`celery beat`):**

| Tarefa                  | Horário/Intervalo    | Descrição                                  |
|-------------------------|---------------------|--------------------------------------------|
| `check_payments`        | 08:00 e 18:00 UTC   | Verifica status de pagamentos no gateway   |
| `generate_invoices`     | 00:00 UTC            | Gera faturas para vencimentos próximos     |
| `block_overdue_accounts`| 01:00 UTC            | Bloqueia contas com faturas vencidas       |
| `check_access_status`   | A cada 5 minutos     | Atualiza `access_status` das subscriptions |

### Regras de Negócio Principais

1. **Trial**: 30 dias gratuitos, fatura gerada 10 dias antes do vencimento
2. **Billing cycle**: 30 dias, fatura gerada quando `next_billing_date` se aproxima
3. **Bloqueio**: 2+ dias de atraso → conta bloqueada, MT5 desconectado
4. **Estratégias**: `low`, `medium`, `high` = livres; `pro`, `expert`, `expert_pro` = requerem unlock
5. **Cópia de trades**: 1:1 exata (low→pro); proporcional (expert_pro)
6. **Provisioning**: sempre `PENDING_PROVISION` → admin confirma → `CONNECTED`

---

## 4. Frontend (React + Vite)

### Estrutura

```
src/
├── App.tsx                # Router principal
├── main.tsx               # Entrypoint
├── index.css              # Design system tokens
├── contexts/
│   └── AuthContext.tsx     # Autenticação (JWT localStorage)
├── hooks/
│   ├── use-api.ts         # Axios wrapper com auth
│   └── use-mobile.tsx     # Detecção responsivo
├── i18n/
│   ├── i18n.ts            # Configuração i18next
│   └── locales/
│       ├── en.json        # Inglês
│       └── pt.json        # Português (Brasil)
├── lib/
│   ├── api.ts             # Axios instance
│   └── utils.ts           # Utilitários
├── pages/
│   ├── Login.tsx
│   ├── Register.tsx
│   ├── ForgotPassword.tsx
│   ├── ResetPassword.tsx
│   ├── Index.tsx           # Landing page
│   ├── TermsOfService.tsx
│   ├── dashboard/
│   │   ├── DashboardHome.tsx
│   │   ├── ConnectMT5.tsx
│   │   ├── Strategies.tsx
│   │   ├── Financial.tsx
│   │   ├── Plans.tsx
│   │   └── SettingsPage.tsx
│   └── admin/
│       ├── AdminPanel.tsx        # Tabs: Users, Plans, Strategies, Subscriptions, Invoices, etc.
│       ├── AdminBilling.tsx
│       ├── OperationsDashboard.tsx
│       └── Provisioning.tsx      # Contas PENDING_PROVISION
└── components/
    ├── DashboardLayout.tsx
    ├── DashboardSidebar.tsx
    ├── ProtectedRoute.tsx
    ├── AdminRoute.tsx
    ├── BillingAccessBanner.tsx   # Banners warning/grace/blocked
    ├── StatCard.tsx
    ├── LanguageSwitcher.tsx
    └── admin/
        ├── StrategiesTab.tsx
        ├── StrategyRequestsTab.tsx
        └── RiskProtectionTab.tsx
```

### Fluxo do Usuário

1. `/register` → Cadastro (nome, email, CPF/CNPJ, senha)
2. `/login` → Login com JWT
3. `/dashboard` → Home com status da conta
4. `/dashboard/connect` → Conectar conta MT5 (login, senha, servidor Exness)
5. `/dashboard/strategies` → Ver/selecionar estratégia
6. `/dashboard/financial` → Faturas e checkout
7. `/dashboard/plans` → Ver planos disponíveis

### Fluxo do Admin

1. `/admin` → Painel com tabs:
   - **Dashboard**: métricas gerais
   - **Users**: buscar, desbloquear, trocar plano
   - **Plans**: CRUD de planos
   - **Strategies**: CRUD + master accounts
   - **Subscriptions**: filtrar por status/access_status, manual override
   - **Invoices**: listar, verificar pagamento, reembolsar
   - **Strategy Requests**: aprovar/rejeitar
   - **Upgrade Requests**: aprovar/rejeitar
   - **Terms**: gerenciar termos de uso
2. `/admin/provisioning` → Contas `PENDING_PROVISION` (reveal senha, confirmar)
3. `/admin/operations` → Dashboard operacional (trades, latência, DLQ)
4. `/admin/billing` → Stats de billing

---

## 5. Agent (Windows VPS)

### Estrutura

```
backend/agent/
├── main.py              # Entrypoint (inicializa todos os processos)
├── config.py            # AgentSettings (pydantic-settings)
├── master_monitor.py    # Monitor de contas master (1 subprocess/master)
├── distributor.py       # Distribui trades para clientes (thread pool)
├── executor.py          # Executa trades no MT5 (1 subprocess/cliente)
├── lot_calculator.py    # Cálculo de lotes (1:1 ou proporcional)
├── result_tracker.py    # Persiste resultados no PostgreSQL
├── db_sync.py           # Sincroniza contas/estratégias do banco
├── instance_manager.py  # Gerencia instâncias MT5 (cópia de pasta)
├── terminal_bootstrap.py # Pré-configura MT5 para primeiro login
└── README.md
```

### Funcionamento

```
Agent (main.py)
│
├── DB Synchronizer (thread, a cada 30s)
│   └── Consulta PostgreSQL para novas contas master/cliente
│   └── Spawna/para processos automaticamente
│   └── Sincroniza balanços
│
├── Master Monitor (1 subprocess por conta master)
│   └── Poll MT5 positions a cada 50ms
│   └── Diff de posições (abertura/fechamento/modificação)
│   └── Publica eventos no Redis
│
├── Trade Distributor (thread pool, 16 threads)
│   └── Consome eventos do Redis
│   └── Calcula lotes (1:1 ou proporcional)
│   └── Enfileira ordens por cliente
│
├── Execution Workers (1 subprocess por conta cliente)
│   └── Desenfileira ordens do Redis (BRPOP)
│   └── Terminal Bootstrap: pré-configura .ini para primeiro login
│   └── Executa no MT5 com controle de slippage
│   └── Retry com backoff exponencial (3 tentativas)
│   └── Dead letter queue para falhas
│
└── Result Tracker (thread)
    └── Persiste resultados no PostgreSQL
```

### Integração com API

O agent se comunica com a API exclusivamente via:
- **PostgreSQL**: leitura de contas, estratégias, status
- **Redis**: pub/sub para comandos e eventos, filas de ordens

O agent **NÃO** faz chamadas HTTP à API.

### Comportamento com `pending_provision`

- O `db_sync.py` ignora contas com `status = 'pending_provision'`
- Nenhum processo é criado para essas contas
- Apenas contas `connected` são processadas
- Contas `blocked` também são ignoradas (nenhum terminal iniciado)

### Regras de Cópia de Trades

| Estratégia    | Tipo de Cópia | Fórmula                                                              |
|---------------|--------------|----------------------------------------------------------------------|
| low           | Exata 1:1    | `volume = master_volume`                                              |
| medium        | Exata 1:1    | `volume = master_volume`                                              |
| high          | Exata 1:1    | `volume = master_volume`                                              |
| pro           | Exata 1:1    | `volume = master_volume`                                              |
| expert        | Exata 1:1    | `volume = master_volume`                                              |
| expert_pro    | Proporcional | `volume = (client_balance / master_balance) × master_volume × risk_multiplier` |

---

## 6. MT5 Provisioning

### Fluxo Completo

```
Usuário                   API                     Admin                    Agent
  │                        │                        │                        │
  │── POST /mt5/connect ──→│                        │                        │
  │                        │ status=PENDING_PROVISION│                        │
  │                        │ (senha criptografada)   │                        │
  │                        │                        │                        │
  │                        │←── GET /provision/pending│                       │
  │                        │                        │                        │
  │                        │←── GET /provision/reveal/{id}                    │
  │                        │  (retorna senha em texto │                       │
  │                        │   claro, AUDIT LOG)      │                       │
  │                        │                        │                        │
  │                        │                        │── Login manual MT5 ──→ │
  │                        │                        │                        │
  │                        │←── POST /provision/complete/{id}                 │
  │                        │  status → CONNECTED     │                       │
  │                        │  dispatch spawn p/ Redis │                       │
  │                        │                        │                        │
  │                        │                        │        ←── Redis sub ──│
  │                        │                        │        Agent detecta   │
  │                        │                        │        e inicia MT5    │
```

### Auditoria

- **Reveal de senha**: `app.audit.provision` logger registra quem, quando e qual conta
- **Provisionamento**: log com email do admin e login MT5
- **Senhas mascaradas**: endpoint `/provision/pending` retorna `••••••••`
- **Reveal restrito**: `require_admin` dependency obrigatória

### Segurança do Provisioning

- Senhas armazenadas com Fernet (AES-128-CBC)
- Chave Fernet compartilhada entre API e Agent (`.env`)
- Endpoint reveal: admin-only + audit log
- Senhas não aparecem em logs normais do backend
- Frontend não expõe senha — admin deve copiar do painel

---

## 7. Billing / Asaas

### Fluxo de Checkout

```
1. Usuário seleciona plano → POST /billing/checkout
   ├── Cria/encontra customer no Asaas
   ├── Cria cobrança (PIX, Boleto ou Cartão)
   ├── Cria Invoice no banco
   └── Retorna URL de pagamento / QR Code PIX

2. Usuário paga → Asaas notifica via webhook
   ├── POST /billing/webhooks/asaas
   ├── Valida token de webhook
   ├── Deduplicação via Payment table
   ├── _handle_payment_confirmation()
   │   ├── Invoice → PAID
   │   ├── Subscription → ACTIVE
   │   ├── access_status → ACTIVE
   │   ├── blocked_at → null
   │   ├── manual_override → false
   │   ├── Avança next_billing_date
   │   └── Reconecta MT5 se estava BLOCKED
   └── Retorna 200 OK

3. Celery worker (2x/dia): check_payments
   └── Consulta Asaas para invoices pendentes
   └── Confirma pagamento se PAID
```

### Gateways Suportados

| Gateway     | Classe            | Métodos             |
|-------------|------------------|----------------------|
| Asaas       | AsaasGateway     | PIX, Boleto, Cartão  |
| Stripe      | StripeGateway    | Cartão, Invoice      |
| MercadoPago | MercadoPagoGateway| PIX                 |
| Celcoin     | CelcoinGateway   | PIX                  |

### Webhook

**URL**: `POST /api/v1/billing/webhooks/asaas`

**Validação**:
- Header `asaas-access-token` deve coincidir com `ASAAS_WEBHOOK_TOKEN`
- Se `ASAAS_WEBHOOK_ENABLED=false`, ignora silenciosamente

**Eventos tratados**:
- `PAYMENT_CONFIRMED` / `PAYMENT_RECEIVED` → marca como pago
- `PAYMENT_OVERDUE` → marca invoice como OVERDUE
- `PAYMENT_REFUNDED` → marca como CANCELLED
- `PAYMENT_DELETED` → marca como CANCELLED

---

## 8. Sistema de Controle de Acesso

### Regras

| Condição                     | `access_status` | Ação                                    |
|------------------------------|-----------------|------------------------------------------|
| 3 dias antes do vencimento   | `warning`       | Banner amarelo no dashboard              |
| Dia do vencimento            | `warning`       | Aviso forte                              |
| Até 2 dias vencido           | `grace`         | Banner laranja, ainda pode operar        |
| 3+ dias vencido              | `blocked`       | Desconecta MT5, impede reconexão         |

### Quando `blocked`:

1. `subscription.status` → `BLOCKED`
2. `subscription.access_status` → `BLOCKED`
3. `subscription.blocked_at` → timestamp atual
4. Todas contas MT5 → status `BLOCKED`
5. Redis pub/sub: envia `stop` para cada conta
6. Redis queue: enfileira `stop` para durabilidade
7. Audit log: registra cada conta bloqueada

### Manual Override (Admin)

- Endpoint: `POST /billing/admin/subscriptions/{id}/override`
- Toggle: liga/desliga `manual_override`
- Quando ativo: access_checker ignora a subscription
- Quando ligado em conta `BLOCKED`: muda para `ACTIVE`, reconecta MT5
- Audit log: registra ON/OFF com email do admin

### Após Pagamento

- `access_status` → `ACTIVE`
- `blocked_at` → null
- `manual_override` → false
- MT5 accounts `BLOCKED` → `CONNECTED`
- Redis: envia `spawn` para reconectar

### Worker `access_checker`

- Roda a cada 5 minutos via Celery Beat
- Consulta apenas subscriptions `ACTIVE` ou `TRIAL` (não `BLOCKED`)
- Ignora subscriptions com `manual_override = true`
- Idempotente: não rebloqueia o que já está bloqueado

---

## 9. API Completa

### Autenticação

| Método | Rota                       | Auth   | Descrição                      |
|--------|---------------------------|--------|--------------------------------|
| POST   | `/auth/register`          | —      | Cadastro de usuário            |
| POST   | `/auth/login`             | —      | Login (retorna JWT)            |
| POST   | `/auth/refresh`           | —      | Refresh token                  |
| GET    | `/auth/me`                | User   | Perfil do usuário              |
| POST   | `/auth/change-password`   | User   | Alterar senha                  |
| POST   | `/auth/forgot-password`   | —      | Solicitar reset de senha       |
| POST   | `/auth/reset-password`    | —      | Executar reset de senha        |

### MT5

| Método | Rota                                | Auth   | Descrição                         |
|--------|-------------------------------------|--------|-----------------------------------|
| POST   | `/mt5/connect`                      | User   | Conectar conta MT5                |
| GET    | `/mt5/accounts`                     | User   | Listar contas MT5 do usuário      |
| DELETE | `/mt5/accounts/{id}`                | User   | Desconectar conta MT5             |

### Estratégias

| Método | Rota                      | Auth   | Descrição                         |
|--------|--------------------------|--------|-----------------------------------|
| GET    | `/strategies/`            | User   | Listar estratégias disponíveis    |
| POST   | `/strategies/select`      | User   | Selecionar estratégia             |
| POST   | `/strategies/request`     | User   | Solicitar estratégia bloqueada    |

### Billing

| Método | Rota                                         | Auth   | Descrição                      |
|--------|----------------------------------------------|--------|--------------------------------|
| GET    | `/billing/plans`                             | —      | Listar planos ativos           |
| GET    | `/billing/subscription`                      | User   | Subscription do usuário        |
| GET    | `/billing/invoices`                          | User   | Faturas do usuário             |
| POST   | `/billing/checkout`                          | User   | Criar checkout/cobrança        |
| GET    | `/billing/checkout/{invoice_id}/status`      | User   | Verificar status do pagamento  |
| GET    | `/billing/upgrade-check`                     | User   | Verificar elegibilidade upgrade|
| POST   | `/billing/upgrade-request`                   | User   | Solicitar upgrade de plano     |
| GET    | `/billing/upgrade-requests`                  | User   | Listar pedidos de upgrade      |
| POST   | `/billing/webhooks/asaas`                    | —      | Webhook Asaas                  |
| POST   | `/billing/webhooks/stripe`                   | —      | Webhook Stripe                 |
| POST   | `/billing/webhooks/mercadopago`              | —      | Webhook MercadoPago            |
| POST   | `/billing/webhooks/celcoin`                  | —      | Webhook Celcoin                |
| GET    | `/billing/admin/stats`                       | Admin  | Estatísticas de billing        |
| GET    | `/billing/admin/subscriptions`               | Admin  | Listar subscriptions           |
| POST   | `/billing/admin/subscriptions/{id}/override` | Admin  | Toggle manual override         |
| POST   | `/billing/admin/subscriptions/{id}/cancel`   | Admin  | Cancelar subscription          |
| GET    | `/billing/admin/invoices`                    | Admin  | Listar todas as faturas        |
| POST   | `/billing/admin/refund`                      | Admin  | Reembolsar fatura              |

### Admin

| Método | Rota                                              | Auth   | Descrição                       |
|--------|----------------------------------------------------|--------|---------------------------------|
| GET    | `/admin/dashboard`                                | Admin  | Dashboard geral                 |
| GET    | `/admin/users`                                    | Admin  | Buscar usuários                 |
| POST   | `/admin/users/{id}/change-plan`                   | Admin  | Trocar plano do usuário         |
| POST   | `/admin/users/{id}/unlock-strategy/{sid}`         | Admin  | Desbloquear estratégia          |
| POST   | `/admin/users/{id}/reset-password`                | Admin  | Reset de senha do usuário       |
| POST   | `/admin/users/{id}/disconnect-mt5/{aid}`          | Admin  | Desconectar MT5                 |
| POST   | `/admin/users/{id}/unblock`                       | Admin  | Desbloquear usuário             |
| GET    | `/admin/users/{id}/invoices`                      | Admin  | Histórico de pagamentos         |
| GET    | `/admin/plans`                                    | Admin  | Listar planos                   |
| POST   | `/admin/plans`                                    | Admin  | Criar plano                     |
| PUT    | `/admin/plans/{id}`                               | Admin  | Atualizar plano                 |
| DELETE | `/admin/plans/{id}`                               | Admin  | Deletar plano                   |
| GET    | `/admin/subscriptions`                            | Admin  | Listar subscriptions            |
| GET    | `/admin/invoices`                                 | Admin  | Listar faturas                  |
| POST   | `/admin/check-payments`                           | Admin  | Verificar pagamentos agora      |
| GET    | `/admin/upgrade-requests`                         | Admin  | Listar pedidos de upgrade       |
| POST   | `/admin/upgrade-requests/{id}`                    | Admin  | Aprovar/rejeitar upgrade        |
| GET    | `/admin/strategies`                               | Admin  | Listar estratégias              |
| POST   | `/admin/strategies`                               | Admin  | Criar estratégia                |
| PUT    | `/admin/strategies/{id}`                          | Admin  | Atualizar estratégia            |
| DELETE | `/admin/strategies/{id}`                          | Admin  | Deletar estratégia              |
| POST   | `/admin/strategies/{id}/master-account`           | Admin  | Definir master account          |
| PUT    | `/admin/strategies/{id}/master-account`           | Admin  | Atualizar master account        |
| GET    | `/admin/strategy-requests`                        | Admin  | Listar pedidos de estratégia    |
| POST   | `/admin/strategy-requests/{id}/approve`           | Admin  | Aprovar pedido                  |
| POST   | `/admin/strategy-requests/{id}/reject`            | Admin  | Rejeitar pedido                 |
| GET    | `/admin/terms`                                    | Admin  | Listar termos                   |
| POST   | `/admin/terms`                                    | Admin  | Criar termos                    |
| PUT    | `/admin/terms/{id}`                               | Admin  | Editar termos                   |
| POST   | `/admin/terms/{id}/activate`                      | Admin  | Ativar versão                   |
| GET    | `/admin/terms/{id}/content`                       | Admin  | Conteúdo completo               |

### Provisioning

| Método | Rota                                 | Auth   | Descrição                      |
|--------|--------------------------------------|--------|--------------------------------|
| GET    | `/admin/provision/pending`           | Admin  | Contas pendentes               |
| GET    | `/admin/provision/reveal/{id}`       | Admin  | Revelar senha (audit logged)   |
| POST   | `/admin/provision/complete/{id}`     | Admin  | Confirmar provisionamento      |
| POST   | `/admin/provision/reset/{id}`        | Admin  | Reset para pending_provision   |

### Risk Protection

| Método | Rota                          | Auth   | Descrição                    |
|--------|-------------------------------|--------|------------------------------|
| GET    | `/admin/risk/settings`        | Admin  | Settings de proteção         |
| PUT    | `/admin/risk/settings`        | Admin  | Atualizar settings           |
| GET    | `/admin/risk/status`          | Admin  | Status de risco em tempo real|
| GET    | `/admin/risk/incidents`       | Admin  | Histórico de incidentes      |
| POST   | `/admin/risk/reset-emergency` | Admin  | Resetar emergência           |
| GET    | `/admin/settings/public`      | —      | Settings públicos            |
| PUT    | `/admin/settings/public`      | Admin  | Atualizar settings públicos  |

### Operations

| Método | Rota                       | Auth   | Descrição                        |
|--------|---------------------------|--------|----------------------------------|
| GET    | `/admin/operations`        | Admin  | Dashboard operacional            |

### Dead Letter Queue

| Método | Rota                                   | Auth   | Descrição                    |
|--------|----------------------------------------|--------|------------------------------|
| GET    | `/admin/dead-letter`                   | Admin  | Listar trades falhados       |
| POST   | `/admin/dead-letter/{id}/retry`        | Admin  | Re-enfileirar para execução  |
| POST   | `/admin/dead-letter/{id}/resolve`      | Admin  | Marcar como resolvido        |

### Legal

| Método | Rota                    | Auth   | Descrição                    |
|--------|------------------------|--------|------------------------------|
| GET    | `/legal/terms`          | —      | Termos ativos                |
| POST   | `/legal/terms/accept`   | User   | Aceitar termos               |
| GET    | `/legal/terms/check`    | User   | Verificar se precisa aceitar |

### Health

| Método | Rota       | Auth   | Descrição      |
|--------|-----------|--------|----------------|
| GET    | `/health`  | —      | Health check   |

---

## 10. Variáveis de Ambiente

### Backend (.env)

```env
# ── Application ───────────────────────────────────
APP_NAME=CopyTrade Pro API          # Nome da aplicação
DEBUG=false                          # Modo debug (true/false)
API_PREFIX=/api/v1                   # Prefixo das rotas
ENVIRONMENT=production               # development | production

# ── Database ──────────────────────────────────────
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/copytrade    # Async (asyncpg)
DATABASE_URL_SYNC=postgresql://user:pass@host:5432/copytrade       # Sync (psycopg2)

# ── Auth ──────────────────────────────────────────
SECRET_KEY=<openssl rand -hex 64>    # Chave JWT (nunca reutilize)
JWT_ALGORITHM=HS256                   # Algoritmo JWT
ACCESS_TOKEN_EXPIRE_MINUTES=60        # Expiração access token
REFRESH_TOKEN_EXPIRE_DAYS=30          # Expiração refresh token

# ── Redis ─────────────────────────────────────────
REDIS_URL=redis://ct-redis:6379/0    # URL do Redis

# ── MT5 Credentials ──────────────────────────────
MT5_CREDENTIAL_KEY=<fernet key>      # Chave Fernet (Fernet.generate_key())
                                      # DEVE ser idêntica no Agent

# ── Asaas ─────────────────────────────────────────
ASAAS_ENABLED=true                    # Ativar Asaas
ASAAS_API_KEY=<api key>              # API key do Asaas
ASAAS_ENVIRONMENT=sandbox             # sandbox | production
ASAAS_SANDBOX=true                    # Alias para sandbox
ASAAS_WEBHOOK_TOKEN=<webhook secret> # Token de validação do webhook
ASAAS_WEBHOOK_ENABLED=true            # Habilitar processamento de webhooks
ASAAS_TIMEOUT_SECONDS=30              # Timeout HTTP para Asaas
ASAAS_BILLING_DUE_DAYS=1              # Dias até vencimento padrão

# ── Stripe (opcional) ────────────────────────────
STRIPE_SECRET_KEY=                    # API key do Stripe
STRIPE_WEBHOOK_SECRET=                # Webhook secret

# ── MercadoPago (opcional) ───────────────────────
MERCADOPAGO_ACCESS_TOKEN=             # Access token

# ── Celcoin (opcional) ───────────────────────────
CELCOIN_CLIENT_ID=                    # Client ID
CELCOIN_CLIENT_SECRET=                # Client Secret

# ── Billing ───────────────────────────────────────
FREE_TRIAL_DAYS=30                    # Dias de trial
INVOICE_GENERATE_BEFORE_DAYS=10       # Gerar fatura X dias antes
INVOICE_DUE_AFTER_DAYS=2              # Vencimento X dias após emissão
BLOCK_AFTER_OVERDUE_DAYS=2            # Bloquear após X dias vencido
SUBSCRIPTION_PRICE=49.90              # Preço default
SUBSCRIPTION_CURRENCY=BRL             # Moeda default

# ── Rate Limiting ────────────────────────────────
LOGIN_RATE_LIMIT=10                   # Máx tentativas por janela
LOGIN_RATE_WINDOW=300                 # Janela em segundos (5min)

# ── CORS ──────────────────────────────────────────
ALLOWED_ORIGINS=http://IP,http://IP:8080   # Origens permitidas (vírgula)

# ── SMTP (opcional) ──────────────────────────────
SMTP_HOST=                            # Servidor SMTP
SMTP_PORT=587                         # Porta SMTP
SMTP_USER=                            # Usuário SMTP
SMTP_PASSWORD=                        # Senha SMTP
SMTP_FROM_EMAIL=                      # Email remetente

# ── Frontend ─────────────────────────────────────
FRONTEND_URL=http://91.98.20.163      # URL do frontend (para links de reset)
```

### Agent (.env — Windows VPS)

```env
DATABASE_URL_SYNC=postgresql://copytrade:admin123@91.98.20.163:5432/copytrade
REDIS_URL=redis://91.98.20.163:6379/0
MT5_CREDENTIAL_KEY=<mesma chave Fernet do backend>
MT5_TERMINAL_PATH=C:\Program Files\MetaTrader 5\terminal64.exe
MT5_BASE_PATH=C:\Program Files\MetaTrader 5
MT5_INSTANCES_DIR=C:\MT5_Instances
```

### Frontend (.env)

```env
VITE_API_URL=http://91.98.20.163/api/v1
```

---

## 11. Instalação Completa (Ubuntu)

### Pré-requisitos

- Ubuntu 22.04+ LTS
- Docker + Docker Compose v2
- Git
- Node.js 18+ (ou Bun)
- Nginx
- PostgreSQL 16 (local ou remoto)

### Passo a Passo

```bash
# 1. Instalar dependências do sistema
apt update && apt install -y docker.io docker-compose-plugin git nginx curl

# 2. Clonar repositório
mkdir -p /opt/copytrade
cd /opt
git clone -b main https://github.com/Eoliveira2025/copy-folio-link.git copytrade
cd /opt/copytrade

# 3. Criar .env do backend
cat > backend/.env << 'EOF'
APP_NAME=CopyTrade Pro API
DEBUG=false
API_PREFIX=/api/v1
ENVIRONMENT=production
DATABASE_URL=postgresql+asyncpg://copytrade:admin123@91.98.20.163:5432/copytrade
DATABASE_URL_SYNC=postgresql://copytrade:admin123@91.98.20.163:5432/copytrade
SECRET_KEY=$(openssl rand -hex 32)
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=30
REDIS_URL=redis://ct-redis:6379/0
MT5_CREDENTIAL_KEY=-RK0mmmLcWul2UvY9jAc9NqMYopVvoWfYmHk9-iDbkk=
ASAAS_ENABLED=true
ASAAS_API_KEY=<sua_api_key>
ASAAS_ENVIRONMENT=sandbox
ASAAS_SANDBOX=true
ASAAS_WEBHOOK_TOKEN=<seu_webhook_secret>
ASAAS_WEBHOOK_ENABLED=true
FREE_TRIAL_DAYS=30
SUBSCRIPTION_PRICE=49.90
SUBSCRIPTION_CURRENCY=BRL
ALLOWED_ORIGINS=http://91.98.20.163,http://91.98.20.163:8080
FRONTEND_URL=http://91.98.20.163
EOF

# 4. Build e start dos containers
docker compose -f docker-compose.restore.yml up -d --build

# 5. Aguardar API
for i in $(seq 1 30); do
    curl -sf http://localhost:8000/health > /dev/null && echo "API OK" && break || sleep 2
done

# 6. Executar migrations
docker exec ct-api-new python -m alembic upgrade head

# 7. Build do frontend
cat > .env << 'EOF'
VITE_API_URL=http://91.98.20.163/api/v1
EOF
npm ci && npm run build

# 8. Configurar Nginx
cat > /etc/nginx/sites-available/copytrade << 'NGINX'
server {
    listen 80;
    server_name _;
    root /opt/copytrade/dist;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /health { proxy_pass http://127.0.0.1:8000; }
    location /docs { proxy_pass http://127.0.0.1:8000; }
    location /redoc { proxy_pass http://127.0.0.1:8000; }
    location /openapi.json { proxy_pass http://127.0.0.1:8000; }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
NGINX

ln -sf /etc/nginx/sites-available/copytrade /etc/nginx/sites-enabled/copytrade
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

# 9. Verificação final
curl -sf http://localhost:8000/health         # API
curl -sf http://localhost/                    # Frontend
docker exec ct-redis redis-cli ping            # Redis
curl -sf -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@copytrade.com","password":"admin123.0@"}'  # Admin login
```

### Admin Default

- Email: `admin@copytrade.com`
- Senha: `admin123.0@`
- Criado automaticamente no primeiro startup da API

---

## 12. Instalação Windows VPS

### Pré-requisitos

- Windows Server 2019/2022
- Python 3.12+
- MetaTrader 5 instalado (`terminal64.exe`)
- Rede aberta para PostgreSQL (5432) e Redis (6379) do Ubuntu

### Passo a Passo

```powershell
# 1. Copiar pasta backend para o VPS
# (via git clone, scp, ou manualmente)

# 2. Instalar dependências
cd backend
pip install -r requirements-agent.txt

# 3. Configurar ambiente
copy agent\.env.example agent\.env
# Editar agent\.env:
#   DATABASE_URL_SYNC=postgresql://copytrade:admin123@91.98.20.163:5432/copytrade
#   REDIS_URL=redis://91.98.20.163:6379/0
#   MT5_CREDENTIAL_KEY=-RK0mmmLcWul2UvY9jAc9NqMYopVvoWfYmHk9-iDbkk=
#   MT5_TERMINAL_PATH=C:\Program Files\MetaTrader 5\terminal64.exe

# 4. Testar conectividade
python -c "import psycopg2; c=psycopg2.connect('postgresql://copytrade:admin123@91.98.20.163:5432/copytrade'); print('DB OK')"
python -c "import redis; r=redis.from_url('redis://91.98.20.163:6379/0'); r.ping(); print('Redis OK')"

# 5. Executar agent
cd backend
python -m agent.main
```

### Configurar como Serviço Windows

```powershell
# Usando NSSM (Non-Sucking Service Manager)
nssm install CopyTradeAgent "C:\Python312\python.exe" "-m agent.main"
nssm set CopyTradeAgent AppDirectory "C:\copytrade\backend"
nssm set CopyTradeAgent AppEnvironmentExtra "MT5_CREDENTIAL_KEY=-RK0mmmLcWul2UvY9jAc9NqMYopVvoWfYmHk9-iDbkk="
nssm start CopyTradeAgent
```

### ⚠️ Importante

- `MT5_CREDENTIAL_KEY` **DEVE** ser idêntica no Ubuntu e Windows
- O agent precisa de acesso de rede às portas 5432 (PG) e 6379 (Redis)
- Firewall: abrir apenas essas portas no Ubuntu
- Cada instância MT5 consome ~50-100MB RAM
- Recomendado: 16GB RAM para ~150 contas simultâneas

---

## 13. Restore e Manutenção

### Script restore.sh

**Localização**: `scripts/restore.sh`

**O que faz**:
1. Para todos containers Docker existentes
2. Mata processos nas portas 8000 e 8080
3. Puxa código mais recente do Git
4. Cria `.env` do backend com todas as credenciais
5. Build do container da API (Docker)
6. Inicia Redis + API
7. Executa migrations (Alembic)
8. Build do frontend (Vite)
9. Configura Nginx
10. Executa health checks (API, Redis, Nginx, login admin)

**O que preserva**:
- Banco de dados (externo, nunca tocado)
- Dados do Redis (se volume persistente)

**O que recria**:
- Containers Docker
- `.env` do backend
- Build do frontend
- Configuração do Nginx

**Execução**:
```bash
chmod +x scripts/restore.sh
sudo ./restore.sh
```

### Atualização do Sistema

```bash
cd /opt/copytrade
git pull origin main
docker compose -f docker-compose.restore.yml build --no-cache ct-api
docker compose -f docker-compose.restore.yml up -d ct-api
docker exec ct-api-new python -m alembic upgrade head
npm ci && npm run build
systemctl reload nginx
```

### Reinício de Serviços

```bash
# API
docker restart ct-api-new

# Redis
docker restart ct-redis

# Nginx
systemctl restart nginx

# Celery (se rodando separado)
docker restart ct-celery ct-celery-beat

# Todos
docker compose -f docker-compose.restore.yml restart
```

### Checklist Pós-Restore

- [ ] `curl http://localhost:8000/health` → `{"status":"ok"}`
- [ ] `curl http://localhost/` → HTML do frontend
- [ ] `curl http://localhost/health` → `{"status":"ok"}` (via Nginx)
- [ ] `docker exec ct-redis redis-cli ping` → `PONG`
- [ ] Login admin funciona
- [ ] `/admin/provisioning` carrega
- [ ] `/docs` (Swagger) acessível

---

## 14. Troubleshooting

### API não responde (porta 8000)

```bash
# Verificar se container está rodando
docker ps | grep ct-api

# Ver logs
docker logs ct-api-new --tail 50

# Verificar porta
ss -tlnp | grep 8000

# Reiniciar
docker restart ct-api-new
```

### Redis em loop de restart

```bash
# Verificar logs
docker logs ct-redis --tail 20

# Causa comum: requirepass configurado mas não usado
# Solução: remover requirepass do docker-compose
docker exec ct-redis redis-cli ping
```

### Migration falha

```bash
# Verificar erro específico
docker exec ct-api-new python -m alembic upgrade head

# Se tabelas já existem:
docker exec ct-api-new python -m alembic stamp head

# Verificar versão atual
docker exec ct-api-new python -m alembic current
```

### Frontend retorna 404

```bash
# Verificar se build existe
ls /opt/copytrade/dist/

# Rebuild
npm run build

# Verificar Nginx
nginx -t
cat /etc/nginx/sites-enabled/copytrade
```

### Senha MT5 não descriptografa

```bash
# Causa: chave Fernet diferente entre API e Agent
# Verificar: comparar MT5_CREDENTIAL_KEY nos dois .env
# A chave DEVE ser idêntica

# Gerar nova chave (se necessário — requer re-criptografar todas as senhas):
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Agent não conecta ao MT5

```
# Windows VPS:
# 1. Verificar se MetaTrader 5 está instalado
# 2. Verificar path em MT5_TERMINAL_PATH
# 3. Verificar se terminal_bootstrap está criando os .ini corretamente
# 4. Testar manualmente: abrir terminal64.exe e fazer login
# 5. Verificar logs do agent: agent.log
```

### Webhook Asaas não funciona

```bash
# Verificar configuração
# 1. ASAAS_WEBHOOK_TOKEN deve coincidir com o configurado no painel Asaas
# 2. URL do webhook no Asaas: http://SEU_IP/api/v1/billing/webhooks/asaas
# 3. Verificar logs:
docker logs ct-api-new | grep -i webhook

# Testar manualmente:
curl -X POST http://localhost:8000/api/v1/billing/webhooks/asaas \
  -H "Content-Type: application/json" \
  -H "asaas-access-token: SEU_TOKEN" \
  -d '{"event":"PAYMENT_CONFIRMED","payment":{"id":"pay_test","value":49.90}}'
```

---

## 15. Segurança

### Senhas MT5

- **Armazenamento**: Fernet (AES-128-CBC) via `cryptography` library
- **Criptografia**: `encrypt_mt5_password()` em `app/core/security.py`
- **Descriptografia**: `decrypt_mt5_password()` — apenas no backend
- **Reveal**: endpoint restrito a admin + audit log
- **Logs**: senhas nunca aparecem em logs (mascaradas com `••••••••`)
- **Frontend**: nunca recebe senha em texto claro (exceto no painel admin provisioning)

### Roles e Permissões

- Roles armazenadas em tabela separada `user_roles` (não na tabela `users`)
- Verificação via `require_admin` dependency (FastAPI)
- Admin verificado via `UserRoleMapping.role == UserRole.ADMIN`
- Não há verificação client-side — sempre server-side

### Auditoria

- **Loggers**: `app.audit.provision`, `app.audit.access_control`
- **Reveal de senha**: registra email do admin + login MT5 + timestamp
- **Bloqueio**: registra cada conta bloqueada/desbloqueada
- **Manual override**: registra ON/OFF + email admin + subscription ID

### JWT

- Algoritmo: HS256
- Access token: 60 minutos
- Refresh token: 30 dias
- Secret key: `openssl rand -hex 64` (não reutilizar)

### Rate Limiting

- Login: 10 tentativas por 5 minutos (por IP)
- Implementado via Redis (`app/middleware/rate_limit.py`)

### CORS

- Em produção: `ALLOWED_ORIGINS` obrigatório (API recusa iniciar sem ele)
- Em desenvolvimento: localhost permitido por padrão

---

## 16. Deploy em Produção

### Domínio e DNS

```bash
# 1. Apontar domínio A record para o IP do servidor
# Exemplo: copytrade.seudominio.com → 91.98.20.163

# 2. Atualizar ALLOWED_ORIGINS no .env
ALLOWED_ORIGINS=https://copytrade.seudominio.com

# 3. Atualizar FRONTEND_URL
FRONTEND_URL=https://copytrade.seudominio.com
```

### SSL com Certbot

```bash
# Instalar Certbot
apt install -y certbot python3-certbot-nginx

# Obter certificado
certbot --nginx -d copytrade.seudominio.com

# Renovação automática (já configurada pelo certbot)
certbot renew --dry-run
```

### Nginx com SSL

```nginx
server {
    listen 80;
    server_name copytrade.seudominio.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name copytrade.seudominio.com;

    ssl_certificate /etc/letsencrypt/live/copytrade.seudominio.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/copytrade.seudominio.com/privkey.pem;

    root /opt/copytrade/dist;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /health { proxy_pass http://127.0.0.1:8000; }
    location /docs { proxy_pass http://127.0.0.1:8000; }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

### Checklist Pré-Deploy

- [ ] `SECRET_KEY` gerada com `openssl rand -hex 64`
- [ ] `MT5_CREDENTIAL_KEY` gerada com `Fernet.generate_key()`
- [ ] `ASAAS_API_KEY` configurada (produção, não sandbox)
- [ ] `ASAAS_ENVIRONMENT=production` e `ASAAS_SANDBOX=false`
- [ ] `ALLOWED_ORIGINS` com domínio correto
- [ ] `DEBUG=false`
- [ ] PostgreSQL com senha forte
- [ ] Redis com senha + bind em interface interna
- [ ] Firewall: 80, 443 público; 5432, 6379 apenas interno
- [ ] SSL configurado
- [ ] Backup do banco configurado

### Checklist Pós-Deploy

- [ ] `curl https://seudominio.com/health` → OK
- [ ] Login admin funciona via HTTPS
- [ ] Cadastro de usuário funciona
- [ ] Painel admin acessível
- [ ] Webhook Asaas atualizado com URL HTTPS
- [ ] Agent no Windows VPS conecta via IP externo
- [ ] Certificado SSL válido (verificar data expiração)

---

## Migrations

| Versão | Arquivo                                      | Descrição                          |
|--------|----------------------------------------------|------------------------------------|
| 000    | `000_initial_schema.py`                      | Schema inicial completo            |
| 001    | `001_add_recurring_billing_fields.py`        | Campos de billing recorrente       |
| 002    | `002_add_trade_table_partitioning.py`        | Particionamento da tabela trades   |
| 003    | `003_add_risk_protection_tables.py`          | Tabelas de proteção de risco       |
| 004    | `004_add_reset_and_dlq_tables.py`            | Reset de senha + DLQ               |
| 005    | `005_add_affiliate_broker_link.py`           | Link de afiliado                   |
| 006    | `006_add_plan_currency.py`                   | Moeda por plano                    |
| 007    | `007_add_min_capital_to_strategies.py`       | Capital mínimo por estratégia      |
| 008    | `008_add_pending_provision_status.py`        | Status PENDING_PROVISION           |
| 009    | `009_add_access_status_to_subscriptions.py`  | Access status + manual override    |

---

## Dependências Python

### Backend (requirements.txt)

```
fastapi==0.111.0
uvicorn[standard]==0.30.1
sqlalchemy==2.0.30
alembic==1.13.1
asyncpg==0.29.0
psycopg2-binary==2.9.9
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.9
pydantic[email-validator]==2.7.4
pydantic-settings==2.3.4
redis==5.0.7
celery==5.4.0
httpx==0.27.0
cryptography==42.0.8
psutil==5.9.8
orjson==3.10.5
```

### Agent (requirements-agent.txt)

```
MetaTrader5
psycopg2-binary
redis
pydantic-settings
cryptography
orjson
psutil
```

---

*Documentação gerada automaticamente. Para dúvidas: consultar `/docs` (Swagger) ou `/redoc`.*
