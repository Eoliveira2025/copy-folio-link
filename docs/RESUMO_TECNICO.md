# CopyTrade Pro — Resumo Técnico Executivo

> **Data:** 2026-04-13 | **Versão:** 1.0

---

## O que é

CopyTrade Pro é uma plataforma SaaS de copy trading automatizado para MetaTrader 5. Replica operações de traders profissionais (contas-mestre) para contas de assinantes em tempo real, com gestão completa de billing, risco e administração.

## Stack Tecnológica

| Camada | Tecnologia |
|--------|------------|
| Frontend | React 18 + TypeScript + Vite + Tailwind CSS + shadcn/ui |
| Backend | Python 3.12 + FastAPI + SQLAlchemy + Pydantic |
| Banco | PostgreSQL 16 |
| Cache | Redis 7 |
| Workers | Celery 5.4 |
| Trading | MetaTrader 5 Python API (Windows VPS) |
| Infra | Docker Compose + Nginx + Certbot |
| Monitoring | Prometheus + Grafana + Loki |
| Payments | Asaas (PIX/Boleto) + Stripe (cartão) |

## Arquitetura

O sistema opera em **duas infraestruturas separadas**:

1. **Ubuntu Server** — API, banco de dados, cache, workers, proxy, monitoramento
2. **Windows VPS** — Execução de trades via MetaTrader 5

A comunicação entre os dois ambientes ocorre via **Redis pub/sub**.

## Módulos Principais

- **Autenticação** — JWT com refresh automático, bcrypt, rate limiting
- **Dashboard** — Gráficos de lucro, conexão MT5, seleção de estratégias
- **Billing** — Planos, checkout, faturas, webhooks Asaas, bloqueio por inadimplência
- **Admin** — Gestão de usuários, estratégias, billing, operações, DLQ, risco
- **Copy Engine** — Motor de cópia de trades com cálculo proporcional de lotes
- **MT5 Manager** — Pool de terminais, provisionamento, watchdog
- **Risk Engine** — Proteção de equity, circuit breakers, incidentes

## Números-Chave

- **10 migrations** de banco (Alembic 000-009)
- **11 rotas de API** (auth, mt5, strategies, billing, admin, legal, risk, operations, dead_letter, admin_provision, settings)
- **13 containers Docker** em produção
- **2 ambientes** separados (Linux + Windows)
- **i18n** em português e inglês

## Para Começar

```bash
# Desenvolvimento rápido
bun install && bun run dev                    # Frontend
cd backend && pip install -r requirements.txt  # Backend
docker compose up -d db redis                  # Infra
alembic upgrade head && uvicorn app.main:app --reload  # API

# Produção
cp .env.production .env && nano .env
./scripts/deploy.sh
```

## Documentação Completa

Veja `docs/DOCUMENTACAO_COMPLETA.md` para instalação detalhada, configuração, troubleshooting e manutenção.
