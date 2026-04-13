# CopyTrade Pro — Documentação Técnica Completa

> **Versão:** 1.0  
> **Data:** 2026-04-13  
> **Confidencial** — Uso exclusivo da equipe técnica.

---

## Sumário

1. [Visão Geral do Sistema](#1-visão-geral-do-sistema)
2. [Estrutura de Pastas](#2-estrutura-de-pastas)
3. [Requisitos para Instalação](#3-requisitos-para-instalação)
4. [Configuração de Ambiente](#4-configuração-de-ambiente)
5. [Instalação Passo a Passo](#5-instalação-passo-a-passo)
6. [Como Rodar em Desenvolvimento](#6-como-rodar-em-desenvolvimento)
7. [Build e Deploy em Produção](#7-build-e-deploy-em-produção)
8. [Banco de Dados](#8-banco-de-dados)
9. [Fluxo Funcional do Sistema](#9-fluxo-funcional-do-sistema)
10. [Processos Internos](#10-processos-internos)
11. [Rotina de Manutenção](#11-rotina-de-manutenção)
12. [Troubleshooting](#12-troubleshooting)
13. [Segurança](#13-segurança)
14. [Checklist Final de Entrega](#14-checklist-final-de-entrega)
15. [Comandos Úteis](#15-comandos-úteis)

---

## 1. Visão Geral do Sistema

### Nome
**CopyTrade Pro**

### Objetivo
Plataforma de copy trading automatizado que replica operações de contas-mestre MetaTrader 5 (MT5) para contas de clientes assinantes, gerenciando todo o ciclo de vida: cadastro, assinatura, billing, conexão MT5, seleção de estratégias e execução de trades.

### Problema que Resolve
Elimina a necessidade de traders manuais operarem cada conta individualmente, automatizando a distribuição de sinais de trading de contas profissionais para múltiplos assinantes com gestão de risco, billing recorrente e administração centralizada.

### Principais Módulos

| Módulo | Descrição |
|--------|-----------|
| **Frontend (React)** | Dashboard do usuário, painel admin, autenticação, seleção de estratégias, billing |
| **Backend API (FastAPI)** | Autenticação JWT, CRUD de usuários/contas/estratégias, billing, webhooks |
| **Celery Workers** | Verificação automática de pagamentos, controle de acesso por inadimplência |
| **Copy Engine** | Motor de cópia de trades: escuta conta-mestre via MT5 API e replica para assinantes |
| **MT5 Manager** | Gerenciador de terminais MT5: pool de instâncias, provisionamento, health checks |
| **Agent (Windows)** | Variante simplificada do engine para rodar nativamente no Windows VPS |

### Arquitetura Geral

```
┌──────────────────────────────────────────────────────┐
│                    UBUNTU SERVER                      │
│                                                       │
│  ┌─────────┐  ┌─────────┐  ┌──────────┐  ┌────────┐ │
│  │  Nginx   │→│ FastAPI  │→│PostgreSQL│  │ Redis  │ │
│  │ (proxy)  │  │  (API)   │  │   (DB)   │  │(cache) │ │
│  └─────────┘  └─────────┘  └──────────┘  └────────┘ │
│                    │                          ↑       │
│  ┌────────────────┐│  ┌────────────┐         │       │
│  │ Celery Worker  ││  │Celery Beat │         │       │
│  └────────────────┘│  └────────────┘         │       │
│                    │                          │       │
│  ┌─────────────────┘                         │       │
│  │  Grafana + Prometheus + Loki (monitoring) │       │
│  └───────────────────────────────────────────┘       │
└──────────────────────────────────────────────────────┘
                          │ Redis pub/sub
┌──────────────────────────────────────────────────────┐
│                  WINDOWS VPS                          │
│                                                       │
│  ┌──────────────┐  ┌────────────────┐                │
│  │ Copy Engine   │  │  MT5 Manager   │                │
│  │ (trade copy)  │  │ (terminal pool)│                │
│  └──────────────┘  └────────────────┘                │
│         ↕                    ↕                        │
│  ┌──────────────────────────────────┐                │
│  │   MetaTrader 5 Terminal(s)       │                │
│  └──────────────────────────────────┘                │
└──────────────────────────────────────────────────────┘
```

### Tecnologias Utilizadas

| Camada | Tecnologia |
|--------|------------|
| Frontend | React 18, TypeScript 5, Vite 5, Tailwind CSS 3, shadcn/ui, React Router 6, React Query, i18next |
| Backend | Python 3.12, FastAPI 0.111, SQLAlchemy 2.0, Pydantic 2.7, Alembic 1.13 |
| Banco de Dados | PostgreSQL 16 |
| Cache/PubSub | Redis 7 |
| Workers | Celery 5.4 |
| MT5 Integration | MetaTrader5 Python API 5.0 (somente no Windows VPS) |
| Containerização | Docker, Docker Compose |
| Proxy/SSL | Nginx 1.25, Certbot (Let's Encrypt) |
| Monitoramento | Prometheus, Grafana 10.4, Loki, Promtail |
| Pagamentos | Asaas (PIX/Boleto), Stripe (cartão internacional) |

---

## 2. Estrutura de Pastas

```
copytrade-pro/
├── src/                          # Frontend React
│   ├── components/               # Componentes reutilizáveis
│   │   ├── ui/                   # shadcn/ui components (Button, Card, Dialog, etc.)
│   │   ├── admin/                # Componentes exclusivos do admin (tabs, tabelas)
│   │   ├── AdminRoute.tsx        # Guard de rota para admin
│   │   ├── ProtectedRoute.tsx    # Guard de rota para usuários autenticados
│   │   ├── DashboardLayout.tsx   # Layout principal do dashboard (sidebar + content)
│   │   ├── DashboardSidebar.tsx  # Sidebar de navegação
│   │   ├── TermsAcceptanceModal.tsx # Modal de aceite de termos
│   │   ├── BillingAccessBanner.tsx  # Banner de inadimplência
│   │   ├── LanguageSwitcher.tsx  # Troca pt/en
│   │   ├── StatCard.tsx          # Card de métricas
│   │   └── NavLink.tsx           # Link de navegação ativo
│   ├── pages/                    # Páginas da aplicação
│   │   ├── Index.tsx             # Landing page
│   │   ├── Login.tsx             # Tela de login
│   │   ├── Register.tsx          # Cadastro (com CPF/CNPJ)
│   │   ├── ForgotPassword.tsx    # Recuperação de senha
│   │   ├── ResetPassword.tsx     # Reset com token
│   │   ├── TermsOfService.tsx    # Página pública de termos
│   │   ├── NotFound.tsx          # 404
│   │   ├── dashboard/            # Páginas do dashboard do usuário
│   │   │   ├── DashboardHome.tsx # Home com gráficos de lucro
│   │   │   ├── ConnectMT5.tsx    # Conexão de conta MT5
│   │   │   ├── Strategies.tsx    # Seleção de estratégias
│   │   │   ├── Plans.tsx         # Planos disponíveis
│   │   │   ├── Financial.tsx     # Faturas e histórico financeiro
│   │   │   └── SettingsPage.tsx  # Configurações do usuário
│   │   └── admin/                # Páginas do painel administrativo
│   │       ├── AdminPanel.tsx    # Gestão de usuários, planos, termos
│   │       ├── AdminBilling.tsx  # Estatísticas e gestão de billing
│   │       ├── OperationsDashboard.tsx # DLQ, métricas do sistema
│   │       └── Provisioning.tsx  # Provisionamento manual de contas MT5
│   ├── contexts/
│   │   └── AuthContext.tsx       # Context de autenticação (login/logout/me)
│   ├── hooks/
│   │   ├── use-api.ts            # Hook de API com React Query
│   │   ├── use-mobile.tsx        # Detecção de mobile
│   │   └── use-toast.ts          # Hook de notificações
│   ├── i18n/
│   │   ├── i18n.ts               # Configuração i18next
│   │   └── locales/
│   │       ├── en.json           # Traduções inglês
│   │       └── pt.json           # Traduções português
│   ├── lib/
│   │   ├── api.ts                # Cliente API (fetch + JWT + refresh)
│   │   └── utils.ts              # Utilidades (cn, formatadores)
│   ├── App.tsx                   # Rotas da aplicação
│   ├── main.tsx                  # Entrypoint React
│   └── index.css                 # Estilos globais + design tokens
│
├── backend/                      # Backend Python
│   ├── app/                      # Aplicação FastAPI principal
│   │   ├── api/
│   │   │   ├── __init__.py       # Agregador de routers
│   │   │   ├── deps.py           # Dependências (get_current_user, get_db)
│   │   │   └── routes/
│   │   │       ├── auth.py       # Login, registro, refresh, forgot/reset password
│   │   │       ├── mt5.py        # Conexão/desconexão de contas MT5
│   │   │       ├── strategies.py # CRUD e seleção de estratégias
│   │   │       ├── billing.py    # Checkout, faturas, planos, webhooks Asaas
│   │   │       ├── admin.py      # Endpoints administrativos
│   │   │       ├── admin_provision.py # Provisionamento manual
│   │   │       ├── legal.py      # Termos de uso (CRUD + aceite)
│   │   │       ├── risk.py       # Configurações de proteção de risco
│   │   │       ├── operations.py # Dashboard operacional
│   │   │       └── dead_letter.py # Fila de trades com falha (DLQ)
│   │   ├── core/
│   │   │   ├── config.py         # Settings via pydantic-settings (.env)
│   │   │   ├── database.py       # Engine SQLAlchemy async
│   │   │   ├── security.py       # Hash de senha, JWT encode/decode
│   │   │   └── logging_config.py # Configuração de logging
│   │   ├── models/               # Modelos SQLAlchemy (tabelas)
│   │   │   ├── user.py           # User + UserRoleMapping (tabela separada)
│   │   │   ├── mt5_account.py    # Contas MT5 conectadas
│   │   │   ├── strategy.py       # Estratégias de trading
│   │   │   ├── strategy_request.py # Solicitações de acesso a estratégias
│   │   │   ├── subscription.py   # Assinaturas
│   │   │   ├── plan.py           # Planos de assinatura
│   │   │   ├── invoice.py        # Faturas
│   │   │   ├── trade.py          # Eventos de trade + cópias
│   │   │   ├── risk.py           # Configurações e incidentes de risco
│   │   │   ├── terms.py          # Termos de uso + aceites
│   │   │   ├── upgrade_request.py # Solicitações de upgrade de plano
│   │   │   ├── dead_letter.py    # Trades com falha
│   │   │   └── password_reset.py # Tokens de reset de senha
│   │   ├── schemas/              # Schemas Pydantic (request/response)
│   │   │   ├── auth.py           # Login, Register, Token
│   │   │   ├── mt5.py            # MT5Connect, MT5Account
│   │   │   ├── strategy.py       # Strategy schemas
│   │   │   ├── billing.py        # Plan, Invoice, Checkout
│   │   │   ├── plan.py           # Plan CRUD schemas
│   │   │   └── legal.py          # Terms schemas
│   │   ├── services/             # Lógica de negócio
│   │   │   ├── copy_engine.py    # Abstração pub/sub → Redis (sem import MT5)
│   │   │   ├── payments.py       # Integração Asaas/Stripe
│   │   │   ├── strategy_switcher.py # Troca de estratégia
│   │   │   └── partition_manager.py # Gerenciamento de partições de trades
│   │   ├── workers/              # Celery tasks
│   │   │   ├── payment_checker.py # Verificação periódica de pagamentos
│   │   │   └── access_checker.py # Bloqueio por inadimplência
│   │   ├── risk_engine/          # Motor de risco
│   │   │   ├── risk_monitor.py   # Monitoramento de risco em tempo real
│   │   │   ├── global_equity_guard.py # Proteção global de equity
│   │   │   └── emergency_executor.py  # Execução de emergência
│   │   ├── middleware/
│   │   │   └── rate_limit.py     # Rate limiting por IP
│   │   └── main.py               # Entrypoint FastAPI (CORS, lifespan, admin seed)
│   │
│   ├── engine/                   # Copy Engine (roda no Windows VPS)
│   │   ├── main.py               # Entrypoint do engine
│   │   ├── config.py             # Configuração do engine
│   │   ├── master_listener.py    # Escuta trades da conta-mestre
│   │   ├── distributor.py        # Distribui trades para assinantes
│   │   ├── executor.py           # Executa trades via MT5 API
│   │   ├── lot_calculator.py     # Cálculo proporcional de lotes
│   │   ├── result_tracker.py     # Rastreamento de resultados
│   │   ├── health_monitor.py     # Health check do engine
│   │   ├── metrics.py            # Métricas Prometheus
│   │   └── models.py             # Modelos do engine
│   │
│   ├── mt5_manager/              # MT5 Terminal Manager (roda no Windows VPS)
│   │   ├── main.py               # Entrypoint
│   │   ├── config.py             # Configuração
│   │   ├── terminal_pool.py      # Pool de terminais MT5
│   │   ├── terminal_process.py   # Processo individual de terminal
│   │   ├── terminal_allocator.py # Alocação de terminais por conta
│   │   ├── account_session.py    # Sessão de conta MT5
│   │   ├── auto_provisioner.py   # Provisionamento automático
│   │   ├── balance_sync.py       # Sincronização de saldo
│   │   ├── credential_vault.py   # Vault de credenciais (Fernet)
│   │   ├── health_monitor.py     # Health check
│   │   └── watchdog.py           # Watchdog de processos
│   │
│   ├── agent/                    # Agent para Windows VPS (alternativa ao Docker)
│   │   ├── main.py               # Entrypoint
│   │   ├── config.py             # Configuração
│   │   ├── distributor.py        # Distribuição de trades
│   │   ├── executor.py           # Execução via MT5
│   │   ├── lot_calculator.py     # Cálculo de lotes
│   │   ├── master_monitor.py     # Monitor da conta-mestre
│   │   ├── instance_manager.py   # Gerenciamento de instâncias MT5
│   │   ├── terminal_bootstrap.py # Bootstrap de terminais
│   │   ├── result_tracker.py     # Rastreamento
│   │   └── db_sync.py            # Sincronização com DB remoto
│   │
│   ├── alembic/                  # Migrações de banco
│   │   ├── env.py                # Configuração Alembic
│   │   ├── script.py.mako        # Template de migrações
│   │   └── versions/
│   │       ├── 000_initial_schema.py        # Schema inicial completo
│   │       ├── 001_add_recurring_billing.py # Campos de billing recorrente
│   │       ├── 002_add_trade_partitioning.py # Particionamento de trades
│   │       ├── 003_add_risk_protection.py   # Tabelas de risco
│   │       ├── 004_add_reset_and_dlq.py     # Reset de senha + DLQ
│   │       ├── 005_add_affiliate_broker.py  # Link de afiliado
│   │       ├── 006_add_plan_currency.py     # Moeda nos planos
│   │       ├── 007_add_min_capital.py       # Capital mínimo em estratégias
│   │       ├── 008_add_pending_provision.py # Status pending_provision
│   │       └── 009_add_access_status.py     # Access status em subscriptions
│   │
│   ├── Dockerfile                # Dockerfile da stack Linux (sem MT5)
│   ├── Dockerfile.mt5            # Dockerfile para Windows VPS / Wine
│   ├── requirements.txt          # Dependências Python (stack Linux)
│   ├── requirements-mt5.txt      # Dependências adicionais MT5
│   ├── requirements-agent.txt    # Dependências do agent Windows
│   ├── alembic.ini               # Configuração Alembic
│   └── docker-compose.yml        # Compose de desenvolvimento
│
├── nginx/                        # Configuração Nginx
│   ├── nginx.conf                # Config principal
│   └── conf.d/
│       ├── default.conf          # Config gerada (não versionar)
│       └── default.conf.template # Template com ${DOMAIN}
│
├── postgres/
│   ├── init.sql                  # Inicialização (extensões, user monitoring)
│   └── postgresql.conf           # Tuning PostgreSQL
│
├── monitoring/
│   ├── prometheus.yml            # Config Prometheus
│   ├── loki.yml                  # Config Loki
│   ├── promtail.yml              # Config Promtail
│   └── grafana/
│       ├── dashboards/           # Dashboards provisionados
│       └── datasources/          # Datasources provisionados
│
├── scripts/
│   ├── deploy.sh                 # Deploy automatizado (SSL + Docker)
│   ├── backup.sh                 # Backup PostgreSQL (cron diário)
│   └── restore.sh                # Restauração completa do sistema
│
├── docs/                         # Documentação técnica
│   ├── ARCHITECTURE.md           # Arquitetura do sistema
│   ├── COPY_ENGINE_ARCHITECTURE.md # Arquitetura do copy engine
│   ├── DEPLOYMENT.md             # Guia de deploy
│   └── TECHNICAL_DOCUMENTATION.md # Documentação técnica geral
│
├── docker-compose.prod.yml       # Stack completa Linux (produção)
├── docker-compose.mt5.yml        # Stack MT5 (Windows VPS)
├── .env.production               # Exemplo de variáveis de produção
├── index.html                    # HTML base do Vite
├── vite.config.ts                # Configuração Vite
├── tailwind.config.ts            # Configuração Tailwind
├── tsconfig.json                 # TypeScript config
└── package.json                  # Dependências frontend
```

---

## 3. Requisitos para Instalação

### Sistema Operacional

| Componente | SO Recomendado |
|-----------|---------------|
| Stack principal (API, DB, Redis, Workers) | Ubuntu 22.04 LTS ou superior |
| MT5 Engine + Manager | Windows Server 2019+ ou Linux com Wine |
| Desenvolvimento local | macOS, Linux ou Windows (com WSL2) |

### Versões de Software

| Software | Versão Mínima | Observação |
|----------|---------------|------------|
| Node.js | 18.x | Recomendado 20.x LTS |
| bun | 1.x | Alternativa ao npm (mais rápido) |
| Python | 3.12 | Obrigatório para backend |
| PostgreSQL | 16 | Via Docker ou instalação nativa |
| Redis | 7.x | Via Docker ou instalação nativa |
| Docker | 24.x+ | Com Docker Compose V2 |
| Nginx | 1.25+ | Apenas produção (via Docker) |
| Git | 2.x | Controle de versão |

### Portas Utilizadas

| Porta | Serviço | Ambiente |
|-------|---------|----------|
| 80 | Nginx HTTP | Produção |
| 443 | Nginx HTTPS | Produção |
| 3000 | Grafana | Produção (interno) |
| 5173 | Vite Dev Server | Desenvolvimento |
| 5432 | PostgreSQL | Todos |
| 6379 | Redis | Todos |
| 8000 | FastAPI | Todos |
| 9090 | Prometheus | Produção (interno) |

### Serviços Externos

| Serviço | Obrigatório | Uso |
|---------|-------------|-----|
| Asaas | Sim (billing) | Pagamento PIX/Boleto (sandbox disponível) |
| Stripe | Opcional | Pagamento cartão internacional |
| SMTP | Opcional | Envio de e-mails (reset de senha) |
| MetaTrader 5 | Sim (trading) | Execução de trades (apenas no Windows VPS) |

---

## 4. Configuração de Ambiente

### Variáveis de Ambiente — Backend (.env)

Crie o arquivo `backend/.env` baseado no exemplo abaixo:

```env
# ── Aplicação ─────────────────────────────────
APP_NAME=CopyTrade Pro API
DEBUG=false                          # true para development
API_PREFIX=/api/v1
ENVIRONMENT=development              # development | production

# ── Banco de Dados ────────────────────────────
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/copytrade
DATABASE_URL_SYNC=postgresql://postgres:postgres@localhost:5432/copytrade

# ── Autenticação JWT ──────────────────────────
SECRET_KEY=gere-com-openssl-rand-hex-64
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60       # Duração do access token
REFRESH_TOKEN_EXPIRE_DAYS=30         # Duração do refresh token

# ── Redis ─────────────────────────────────────
REDIS_URL=redis://localhost:6379/0

# ── Criptografia MT5 ─────────────────────────
# Gerar com: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
MT5_CREDENTIAL_KEY=sua-chave-fernet-aqui

# ── Pagamentos — Asaas ────────────────────────
ASAAS_ENABLED=true
ASAAS_API_KEY=                       # Obtido no painel Asaas
ASAAS_ENVIRONMENT=sandbox            # sandbox | production
ASAAS_SANDBOX=true                   # true = sandbox, false = production
ASAAS_BASE_URL=                      # Deixe vazio para auto-detectar
ASAAS_WEBHOOK_TOKEN=                 # Token de validação de webhooks
ASAAS_WEBHOOK_ENABLED=true
ASAAS_TIMEOUT_SECONDS=30
ASAAS_BILLING_DUE_DAYS=1

# ── Pagamentos — Stripe (opcional) ────────────
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=

# ── Billing ───────────────────────────────────
FREE_TRIAL_DAYS=30                   # Dias de trial gratuito
INVOICE_GENERATE_BEFORE_DAYS=10      # Gerar fatura X dias antes do vencimento
INVOICE_DUE_AFTER_DAYS=2             # Vencimento da fatura
BLOCK_AFTER_OVERDUE_DAYS=2           # Bloquear acesso após X dias de atraso
SUBSCRIPTION_PRICE=49.90
SUBSCRIPTION_CURRENCY=BRL            # BRL ou USD

# ── Rate Limiting ────────────────────────────
LOGIN_RATE_LIMIT=5                   # Tentativas por janela
LOGIN_RATE_WINDOW=300                # Janela em segundos (5 min)

# ── CORS ─────────────────────────────────────
# Em produção, listar origens permitidas separadas por vírgula
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000

# ── SMTP (opcional) ──────────────────────────
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=

# ── Frontend URL ─────────────────────────────
FRONTEND_URL=http://localhost:5173
```

### Variáveis de Ambiente — Frontend (.env)

Crie na raiz do projeto:

```env
VITE_API_URL=http://localhost:8000/api/v1
```

### Variáveis de Ambiente — MT5 (Windows VPS)

Crie `backend/agent/.env`:

```env
DATABASE_URL_SYNC=postgresql://user:pass@IP_SERVIDOR:5432/copytrade
REDIS_URL=redis://:REDIS_PASSWORD@IP_SERVIDOR:6379/0
MT5_CREDENTIAL_KEY=mesma-chave-do-backend
MT5_TERMINAL_PATH=C:\Program Files\MetaTrader 5\terminal64.exe
MT5_BASE_PATH=C:\Program Files\MetaTrader 5
MT5_INSTANCES_DIR=C:\MT5_Instances
MT5_INSTANCE_MAPPING_FILE=C:\MT5_Instances\instances.json
MT5_INIT_TIMEOUT_MS=60000
MASTER_POLL_INTERVAL_MS=50
MAX_SLIPPAGE_POINTS=30
DB_SYNC_INTERVAL_S=30
```

### Diferenças entre Ambientes

| Variável | Desenvolvimento | Produção |
|----------|----------------|----------|
| `DEBUG` | `true` | `false` |
| `ENVIRONMENT` | `development` | `production` |
| `ALLOWED_ORIGINS` | `http://localhost:5173` | `https://seudominio.com` |
| `ASAAS_SANDBOX` | `true` | `false` |
| `SECRET_KEY` | Qualquer valor | Chave forte (64 hex chars) |
| `DATABASE_URL` | localhost | Container ou IP do servidor |

---

## 5. Instalação Passo a Passo

### 5.1 Frontend

```bash
# Clonar o repositório
git clone https://github.com/seu-repo/copytrade-pro.git
cd copytrade-pro

# Instalar dependências (usando bun — recomendado)
bun install

# Ou usando npm
npm install

# Criar arquivo de ambiente
echo "VITE_API_URL=http://localhost:8000/api/v1" > .env

# Verificar instalação
bun run build
# Resultado esperado: pasta dist/ criada com os arquivos estáticos
```

**Possíveis erros:**
- `bun: command not found` → Instale: `curl -fsSL https://bun.sh/install | bash`
- `node version mismatch` → Use nvm: `nvm use 20`

### 5.2 Backend

```bash
cd backend

# Criar virtualenv
python3.12 -m venv venv
source venv/bin/activate  # Linux/macOS
# ou: venv\Scripts\activate  # Windows

# Instalar dependências
pip install -r requirements.txt

# Criar arquivo de ambiente
cp ../.env.production .env
# Editar .env com suas credenciais

# Verificar instalação
python -c "from app.main import app; print('OK')"
# Resultado esperado: "OK" sem erros
```

**Possíveis erros:**
- `pg_config not found` → Instalar: `sudo apt install libpq-dev`
- `ModuleNotFoundError: No module named 'app'` → Verifique se está no diretório `backend/`

### 5.3 Banco de Dados

```bash
# Opção 1: Via Docker (recomendado)
cd backend
docker compose up -d db redis

# Opção 2: PostgreSQL nativo
sudo -u postgres psql -c "CREATE DATABASE copytrade;"
sudo -u postgres psql -c "CREATE USER copytrade_user WITH PASSWORD 'sua-senha';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE copytrade TO copytrade_user;"

# Aplicar extensões
psql -U postgres -d copytrade -f ../postgres/init.sql

# Aplicar migrações
cd backend
alembic upgrade head
# Resultado esperado: "Running upgrade ... -> head" sem erros
```

**Possíveis erros:**
- `KeyError: '005_add_affiliate_broker_link'` → Verifique que todas as migrations 000-009 existem em `alembic/versions/`
- `cannot drop table trade_events_old` → A migration 002 já inclui `CASCADE`; se persistir, aplique manualmente

### 5.4 Seed do Admin

O admin padrão é criado automaticamente ao iniciar o backend:

- **Email:** `admin@copytrade.com`
- **Senha:** `admin123.0@`

> ⚠️ **IMPORTANTE:** Altere essas credenciais imediatamente após o primeiro login em produção.

---

## 6. Como Rodar em Desenvolvimento

### Iniciar Backend

```bash
cd backend
source venv/bin/activate

# Iniciar PostgreSQL e Redis via Docker
docker compose up -d db redis

# Aplicar migrações
alembic upgrade head

# Iniciar API
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Resultado esperado:
# INFO: Uvicorn running on http://0.0.0.0:8000
# INFO: Default admin user created (admin@copytrade.com)
```

### Iniciar Frontend

```bash
# Em outro terminal, na raiz do projeto
bun run dev

# Resultado esperado:
# VITE v5.x.x ready in Xms
# ➜ Local: http://localhost:5173/
```

### URLs de Acesso (Desenvolvimento)

| Recurso | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| API | http://localhost:8000/api/v1 |
| API Docs (Swagger) | http://localhost:8000/docs |
| API Docs (ReDoc) | http://localhost:8000/redoc |
| Health Check | http://localhost:8000/health |

### Verificar Funcionamento

```bash
# Health check da API
curl http://localhost:8000/health
# Esperado: {"status":"ok","service":"CopyTrade Pro API"}

# Testar login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@copytrade.com","password":"admin123.0@"}'
# Esperado: {"access_token":"...","refresh_token":"..."}
```

### Modo Debug

Defina `DEBUG=true` no `.env` para:
- Logs detalhados do SQLAlchemy (queries SQL)
- Stack traces completos nos erros da API
- CORS permissivo (origens localhost)

---

## 7. Build e Deploy em Produção

### 7.1 Preparação do Servidor Ubuntu

```bash
# Instalar Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Instalar Docker Compose V2
sudo apt install docker-compose-plugin

# Verificar
docker --version
docker compose version
```

### 7.2 Configuração Inicial

```bash
# Clonar repositório
git clone https://github.com/seu-repo/copytrade-pro.git /opt/copytrade
cd /opt/copytrade

# Criar .env de produção
cp .env.production .env

# Editar com credenciais reais
nano .env
# OBRIGATÓRIO alterar:
#   DOMAIN=seudominio.com
#   POSTGRES_PASSWORD=senha-forte
#   SECRET_KEY=chave-forte-64-hex
#   GRAFANA_PASSWORD=senha-grafana
```

### 7.3 Deploy Automatizado

```bash
chmod +x scripts/deploy.sh
./scripts/deploy.sh
```

O script executa automaticamente:
1. Validação de pré-requisitos (Docker, .env)
2. Geração da config Nginx
3. Obtenção de certificado SSL (Let's Encrypt)
4. Build das imagens Docker
5. Início de todos os serviços
6. Aplicação de migrações
7. Configuração de backup automático

### 7.4 Configuração de Domínio

1. **DNS:** Aponte um registro `A` para o IP do servidor
2. **www:** Adicione CNAME `www` → `seudominio.com`
3. **SSL:** O script `deploy.sh` obtém certificado automaticamente via Certbot
4. **Renovação:** O container `certbot` renova automaticamente a cada 12h

### 7.5 Serviços em Produção

| Container | Descrição | Portas |
|-----------|-----------|--------|
| ct-nginx | Reverse proxy + SSL | 80, 443 |
| ct-api | FastAPI (4 workers) | 8000 (interno) |
| ct-celery-worker | Celery worker (4 threads) | — |
| ct-celery-beat | Celery scheduler | — |
| ct-postgres | PostgreSQL 16 | 5432 (interno) |
| ct-redis | Redis 7 | 6379 (interno) |
| ct-prometheus | Métricas | 9090 (interno) |
| ct-grafana | Dashboards | 3000 (interno) |
| ct-loki | Agregação de logs | 3100 (interno) |
| ct-promtail | Coleta de logs | — |
| ct-node-exporter | Métricas do host | — |
| ct-db-backup | Backup diário (03:00 UTC) | — |
| ct-certbot | Renovação SSL | — |

### 7.6 Build do Frontend para Produção

```bash
# Na raiz do projeto
echo "VITE_API_URL=https://seudominio.com/api/v1" > .env
bun run build

# Copiar dist/ para o volume static_files do Nginx
docker cp dist/. ct-nginx:/var/www/static/
```

### 7.7 Monitoramento

- **Grafana:** `https://seudominio.com/grafana/`
- **Credenciais:** Definidas em `GRAFANA_USER` / `GRAFANA_PASSWORD`
- **Dashboards pré-configurados:** Node Exporter, API metrics, PostgreSQL

---

## 8. Banco de Dados

### 8.1 Engine

PostgreSQL 16 com extensões:
- `uuid-ossp` — Geração de UUIDs
- `pg_trgm` — Busca por similaridade de texto

### 8.2 Tabelas Principais

| Tabela | Descrição |
|--------|-----------|
| `users` | Dados de usuários (email, senha hash, nome) |
| `user_roles` | Papéis de usuário (admin, user) — tabela separada por segurança |
| `mt5_accounts` | Contas MT5 conectadas (login, servidor, credenciais criptografadas) |
| `strategies` | Estratégias de trading disponíveis |
| `user_strategies` | Relação usuário ↔ estratégia |
| `strategy_requests` | Solicitações de acesso a estratégias |
| `plans` | Planos de assinatura (nome, preço, moeda) |
| `subscriptions` | Assinaturas ativas (status, access_status, trial, manual_override) |
| `invoices` | Faturas geradas (Asaas/Stripe) |
| `trade_events` | Eventos de trade da conta-mestre (particionada por mês) |
| `trade_copies` | Cópias executadas nas contas de assinantes |
| `risk_settings` | Configurações globais de risco |
| `risk_incidents` | Incidentes de risco registrados |
| `terms_of_service` | Versões dos termos de uso |
| `terms_acceptances` | Aceites registrados |
| `password_resets` | Tokens de reset de senha |
| `dead_letter_trades` | Trades com falha para reprocessamento |
| `upgrade_requests` | Solicitações de upgrade de plano |

### 8.3 Migrações

```bash
# Aplicar todas as migrações
cd backend
alembic upgrade head

# Ver status atual
alembic current

# Criar nova migração
alembic revision --autogenerate -m "descricao_da_mudanca"

# Reverter última migração
alembic downgrade -1
```

### 8.4 Backup

O backup automático é executado diariamente às 03:00 UTC pelo container `ct-db-backup`:

```bash
# Backup manual
docker compose -f docker-compose.prod.yml exec db-backup /backup.sh

# Listar backups
docker compose -f docker-compose.prod.yml exec db-backup ls -la /backups/
```

**Retenção:** 30 dias (configurável em `scripts/backup.sh`).

### 8.5 Restauração

```bash
# Restaurar de backup
docker compose -f docker-compose.prod.yml exec db psql -U $POSTGRES_USER -d $POSTGRES_DB \
  < /backups/copytrade_YYYYMMDD_HHMMSS.sql.gz

# Ou usar o script de restauração completa
chmod +x scripts/restore.sh
sudo ./scripts/restore.sh
```

---

## 9. Fluxo Funcional do Sistema

### 9.1 Fluxo do Usuário

```
1. Registro → Cadastro com email, senha, CPF/CNPJ
2. Login → JWT (access + refresh token)
3. Aceite de Termos → Modal obrigatório no primeiro acesso
4. Dashboard → Visão geral de lucro e trades
5. Conectar MT5 → Login, senha, servidor (ex: Exness-MT5Trial14)
6. Selecionar Plano → Escolher plano e forma de pagamento
7. Checkout → Gerar fatura Asaas (PIX/Boleto)
8. Pagamento → Webhook Asaas confirma pagamento
9. Selecionar Estratégia → Escolher estratégia de copy trading
10. Trades Automáticos → Copy engine replica trades da conta-mestre
```

### 9.2 Fluxo de Autenticação

```
Login (email + senha)
  → API verifica hash bcrypt
  → Gera access_token (60 min) + refresh_token (30 dias)
  → Frontend armazena em localStorage
  → A cada request: Authorization: Bearer <access_token>
  → Se 401: tenta refresh automático
  → Se refresh falha: redireciona para /login
```

### 9.3 Fluxo de Billing

```
Usuário seleciona plano → API cria subscription (trial ou pago)
  → Se pago: API chama Asaas para criar cobrança (PIX/Boleto)
  → Retorna URL de pagamento
  → Webhook Asaas notifica pagamento confirmado
  → API atualiza invoice.status = "paid"
  → Celery worker verifica periodicamente (payment_checker)
  → Se inadimplente: access_status = "suspended"
  → Frontend exibe BillingAccessBanner bloqueando acesso
```

### 9.4 Fluxo de Copy Trading

```
Conta-mestre abre trade
  → Copy Engine detecta via polling (50ms)
  → Publica evento no Redis (copytrade:trades)
  → Distributor calcula lotes proporcionais por assinante
  → Executor abre trades nas contas dos assinantes via MT5 API
  → Result tracker registra no PostgreSQL
  → Se falha: trade vai para Dead Letter Queue (DLQ)
```

### 9.5 Comunicação Frontend ↔ Backend

- **Protocolo:** HTTP REST (JSON)
- **Autenticação:** JWT Bearer token
- **Base URL:** `{origin}/api/v1` (auto-detectado ou via `VITE_API_URL`)
- **Refresh automático:** Transparente no `api.ts`
- **Error handling:** Classe `ApiError` com status code e mensagem
- **Estado:** React Query (cache 30s, retry 1x)

---

## 10. Processos Internos

### 10.1 Autenticação e Autorização

- **Hash de senha:** bcrypt via `passlib`
- **JWT:** `python-jose` com HMAC-SHA256
- **Roles:** Tabela separada `user_roles` (previne privilege escalation)
- **Admin check:** Via query na tabela `user_roles`, nunca pelo profile
- **Rate limiting:** 5 tentativas de login por 5 minutos (por IP)

### 10.2 Criptografia de Credenciais MT5

- **Algoritmo:** Fernet (AES-128-CBC + HMAC-SHA256)
- **Chave:** Configurada via `MT5_CREDENTIAL_KEY`
- **Armazenamento:** Credenciais MT5 criptografadas no banco
- **Decriptação:** Apenas no momento de conectar ao terminal MT5

### 10.3 Celery Workers

| Task | Intervalo | Descrição |
|------|-----------|-----------|
| `payment_checker` | A cada 1h | Verifica status de pagamentos pendentes no Asaas |
| `access_checker` | A cada 30min | Bloqueia/desbloqueia acesso por inadimplência |

### 10.4 Redis — Uso

| Uso | Canal/Chave | Descrição |
|-----|-------------|-----------|
| Celery broker | `celery` | Fila de tarefas |
| PubSub | `copytrade:terminal:commands` | Comandos API → MT5 Manager |
| PubSub | `copytrade:engine:commands` | Comandos API → Copy Engine |
| Cache | `rate_limit:*` | Contadores de rate limiting |

### 10.5 Monitoramento

- **Prometheus:** Coleta métricas a cada 15s
- **Grafana:** Dashboards pré-configurados
- **Loki + Promtail:** Agregação centralizada de logs
- **Node Exporter:** Métricas do host (CPU, memória, disco)

---

## 11. Rotina de Manutenção

### Atualizar o Sistema

```bash
cd /opt/copytrade
git pull origin main
docker compose -f docker-compose.prod.yml build --parallel
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml exec api alembic upgrade head
```

### Atualizar Dependências Frontend

```bash
bun update
bun run build
```

### Atualizar Dependências Backend

```bash
cd backend
pip install --upgrade -r requirements.txt
```

### Reiniciar com Segurança

```bash
# Reiniciar serviço específico
docker compose -f docker-compose.prod.yml restart api

# Reiniciar toda a stack (sem perder dados)
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d
```

### Verificar Logs

```bash
# Logs de um serviço
docker compose -f docker-compose.prod.yml logs -f api
docker compose -f docker-compose.prod.yml logs -f celery-worker

# Últimas 100 linhas
docker compose -f docker-compose.prod.yml logs --tail 100 api
```

### Verificar Saúde do Sistema

```bash
# Health check API
curl -sf https://seudominio.com/health

# Status dos containers
docker compose -f docker-compose.prod.yml ps

# Uso de recursos
docker stats --no-stream
```

### Rollback

```bash
# Voltar para versão anterior do código
git log --oneline -5
git checkout <commit-hash>
docker compose -f docker-compose.prod.yml build api
docker compose -f docker-compose.prod.yml up -d api

# Reverter última migração
docker compose -f docker-compose.prod.yml exec api alembic downgrade -1
```

---

## 12. Troubleshooting

### Erro de Dependência

**Problema:** `ModuleNotFoundError: No module named 'MetaTrader5'`  
**Causa:** Pacote MT5 sendo importado na stack Linux  
**Solução:** Garantir que `requirements.txt` (Linux) NÃO contém `MetaTrader5`. Esse pacote está apenas em `requirements-mt5.txt`.

---

**Problema:** `pg_config executable not found`  
**Causa:** Falta `libpq-dev`  
**Solução:** `sudo apt install libpq-dev python3-dev`

---

### Erro de Build

**Problema:** Build do Docker falha com `MetaTrader5==5.0.4230`  
**Causa:** Stack Linux tentando instalar pacote Windows-only  
**Solução:** A stack Linux usa `Dockerfile` + `requirements.txt` (sem MT5). Verifique que não está usando `Dockerfile.mt5`.

---

### Erro de Conexão com Banco

**Problema:** `connection refused` para PostgreSQL  
**Causa:** Container do banco não está rodando ou credenciais incorretas  
**Solução:**
```bash
docker compose -f docker-compose.prod.yml ps db
docker compose -f docker-compose.prod.yml logs db
# Verificar credenciais no .env
```

---

### Erro de Migração

**Problema:** `KeyError: '005_add_affiliate_broker_link'`  
**Causa:** Arquivo de migração ausente ou corrompido  
**Solução:** Verificar que todos os arquivos 000-009 existem em `alembic/versions/`

---

**Problema:** `cannot drop table trade_events_old`  
**Causa:** Foreign key impede DROP  
**Solução:** A migration 002 já usa `CASCADE`. Se persistir: `DROP TABLE trade_events_old CASCADE;`

---

### Erro de CORS

**Problema:** `Access-Control-Allow-Origin` bloqueando requests  
**Causa:** `ALLOWED_ORIGINS` não inclui a origem do frontend  
**Solução:** Adicionar a URL do frontend em `ALLOWED_ORIGINS` no `.env`

---

### Erro de Autenticação

**Problema:** `401 Unauthorized` em todas as requests  
**Causa:** Token expirado ou `SECRET_KEY` diferente entre deploys  
**Solução:** Fazer logout e login novamente. Garantir que `SECRET_KEY` não mudou.

---

### Erro de Porta Ocupada

**Problema:** `bind: address already in use`  
**Solução:**
```bash
# Identificar processo
sudo lsof -i :8000
# Matar processo
sudo fuser -k 8000/tcp
```

---

### Erro de Deploy

**Problema:** SSL certificate not found  
**Causa:** Certbot não conseguiu emitir certificado  
**Solução:** Verificar que o DNS aponta para o servidor e porta 80 está acessível

---

## 13. Segurança

### Proteção de .env

- **NUNCA** comitar `.env` no Git (já está no `.gitignore`)
- Usar permissões restritas: `chmod 600 .env`
- Rotacionar `SECRET_KEY` periodicamente (invalida todos os JWTs)

### Armazenamento de Segredos

- Senhas hasheadas com bcrypt (custo 12)
- Credenciais MT5 criptografadas com Fernet (AES-128-CBC)
- Chave Fernet armazenada apenas no `.env` do servidor

### Permissões

- Roles em tabela separada (`user_roles`), nunca no perfil do usuário
- Admin verificado por query no banco, nunca por `localStorage`
- Rate limiting no login: 5 tentativas / 5 minutos

### Headers de Segurança (Nginx)

- HTTPS obrigatório (redirect 301)
- TLS 1.2+ apenas
- HSTS recomendado (adicionar em nginx.conf)
- CORS restritivo em produção

### Acesso ao Banco

- Usuário `monitoring` com permissão somente leitura
- Credenciais do PostgreSQL nunca expostas ao frontend
- Conexões via rede Docker interna (não expostas externamente em produção)

### Logs Sensíveis

- Senhas nunca logadas (nem em debug)
- Tokens JWT nunca logados por completo
- Credenciais MT5 logadas apenas como `[ENCRYPTED]`

### Práticas Recomendadas para Produção

1. Alterar admin padrão imediatamente
2. Usar `SECRET_KEY` gerada com `openssl rand -hex 64`
3. Desabilitar `/docs` e `/redoc` em produção (opcional)
4. Configurar firewall (ufw) para permitir apenas portas 80/443/22
5. Manter Docker e imagens atualizados
6. Monitorar logs via Grafana/Loki
7. Backup diário ativo e testado

---

## 14. Checklist Final de Entrega

- [x] Projeto empacotado e organizado
- [x] Variáveis de ambiente documentadas (.env.production, agent/.env.example)
- [x] Dependências instaláveis (package.json, requirements.txt)
- [x] Build funcional (frontend e backend)
- [x] Docker Compose funcional (dev e prod)
- [x] Migrações aplicáveis em banco limpo (000-009)
- [x] Admin padrão criado automaticamente
- [x] Documentação técnica completa
- [x] Scripts de deploy, backup e restauração
- [x] Monitoramento configurado (Prometheus, Grafana, Loki)
- [x] Separação Linux ↔ Windows VPS (sem dependência MT5 no Ubuntu)
- [x] Nginx com SSL via Certbot
- [x] Estrutura revisada e limpa

### Pendências Conhecidas

- [ ] Configurar SMTP para envio de e-mails de reset de senha
- [ ] Testes automatizados do backend (unitários e integração)
- [ ] CI/CD pipeline (GitHub Actions)
- [ ] Rate limiting mais granular por endpoint
- [ ] Documentação de API (OpenAPI) personalizada

---

## 15. Comandos Úteis

### Frontend

```bash
bun install              # Instalar dependências
bun run dev              # Iniciar servidor de desenvolvimento
bun run build            # Build de produção
bun run lint             # Verificar código
bun run test             # Rodar testes
bun run preview          # Preview do build
```

### Backend

```bash
# Virtualenv
source venv/bin/activate

# Servidor de desenvolvimento
uvicorn app.main:app --reload --port 8000

# Migrações
alembic upgrade head           # Aplicar todas
alembic downgrade -1           # Reverter última
alembic current                # Ver estado atual
alembic revision --autogenerate -m "msg"  # Nova migração

# Celery
celery -A app.workers.payment_checker worker --loglevel=info
celery -A app.workers.payment_checker beat --loglevel=info
```

### Docker (Produção)

```bash
# Subir stack completa
docker compose -f docker-compose.prod.yml up -d

# Parar tudo
docker compose -f docker-compose.prod.yml down

# Rebuild
docker compose -f docker-compose.prod.yml build --parallel

# Logs
docker compose -f docker-compose.prod.yml logs -f api
docker compose -f docker-compose.prod.yml logs -f celery-worker

# Status
docker compose -f docker-compose.prod.yml ps

# Backup manual
docker compose -f docker-compose.prod.yml exec db-backup /backup.sh

# Migração em produção
docker compose -f docker-compose.prod.yml exec api alembic upgrade head

# Shell no container
docker compose -f docker-compose.prod.yml exec api bash
docker compose -f docker-compose.prod.yml exec db psql -U postgres -d copytrade
```

### Deploy

```bash
./scripts/deploy.sh          # Deploy automatizado
./scripts/restore.sh         # Restauração completa
```

---

> **Documento gerado em 2026-04-13 — CopyTrade Pro v1.0**
