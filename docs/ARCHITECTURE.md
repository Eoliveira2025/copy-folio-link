# CopyTrade Pro — Full Architecture Documentation

## System Overview

CopyTrade Pro is a multi-service copy trading platform that replicates trades from professional master MT5 accounts to subscriber client accounts in real-time.

```
┌─────────────────────────────────────────────────────────────────┐
│                     UBUNTU SERVER (Hetzner)                     │
│                                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────┐   │
│  │  Nginx   │  │ FastAPI  │  │PostgreSQL│  │    Redis       │   │
│  │ (proxy)  │──│  (API)   │──│  (data)  │  │ (pub/sub +    │   │
│  │          │  │          │  │          │  │  queues)       │   │
│  └──────────┘  └──────────┘  └──────────┘  └───────┬───────┘   │
│       │                                            │           │
│  ┌──────────┐                                      │           │
│  │  React   │                          Redis connection        │
│  │ Frontend │                                      │           │
│  └──────────┘                                      │           │
└────────────────────────────────────────────────────│───────────┘
                                                     │
                                          VPN / mTLS │
                                                     │
┌────────────────────────────────────────────────────│───────────┐
│                   WINDOWS VPS (Hetzner)            │           │
│                                                    │           │
│  ┌─────────────────────┐  ┌────────────────────────┴────────┐ │
│  │   Copy Engine        │  │    MT5 Terminal Manager         │ │
│  │                      │  │                                 │ │
│  │ ┌─────────────────┐  │  │ ┌──────────┐ ┌──────────┐      │ │
│  │ │ Master Listener │──│──│ │Terminal 1│ │Terminal 2│ ...  │ │
│  │ │ (10ms polling)  │  │  │ │ (50 accs)│ │ (50 accs)│      │ │
│  │ └────────┬────────┘  │  │ └──────────┘ └──────────┘      │ │
│  │          │            │  │                                 │ │
│  │ ┌────────▼────────┐  │  │ ┌──────────┐ ┌──────────┐      │ │
│  │ │  Distributor    │  │  │ │ Watchdog │ │BalSync   │      │ │
│  │ │ (fan-out)       │  │  │ └──────────┘ └──────────┘      │ │
│  │ └────────┬────────┘  │  └─────────────────────────────────┘ │
│  │ ┌────────▼────────┐  │                                      │
│  │ │  Executor Pool  │  │                                      │
│  │ │ (MT5 API calls) │  │                                      │
│  │ └─────────────────┘  │                                      │
│  └──────────────────────┘                                      │
└────────────────────────────────────────────────────────────────┘
```

---

## Component Details

### 1. Ubuntu Server Services

#### FastAPI Backend (`backend/app/`)
- **Auth**: JWT-based with access/refresh tokens
- **Admin**: User management, plan CRUD, strategy CRUD, master account management
- **Billing**: Plans, subscriptions, invoices, payment gateway integration (Stripe/Asaas/MercadoPago)
- **MT5 Endpoints**: Account connection, strategy selection
- **Risk**: Global drawdown protection, emergency stop

#### PostgreSQL Database
Key tables:
- `users` — User accounts
- `plans` — Subscription plans with `allowed_strategies` (JSON array) and `currency` (USD/BRL)
- `subscriptions` — User subscriptions linked to plans
- `invoices` — Billing invoices
- `strategies` — Strategy definitions (level, risk_multiplier, requires_unlock)
- `master_accounts` — 1:1 with strategies, stores MT5 credentials for master accounts
- `mt5_accounts` — User MT5 accounts (encrypted passwords)
- `user_strategies` — User↔Strategy activation tracking
- `trade_events` — Master account trade events
- `trade_copies` — Copies executed on client accounts
- `dead_letter_trades` — Failed trades for retry

#### Redis
- **Pub/Sub channels**: `copytrade:events:{master_id}` — Real-time trade events from master listeners
- **Execution queues**: `copytrade:execute:{client_mt5_id}` — Per-client copy orders
- **Dead letter**: `copytrade:dead_letter` — Failed executions for retry
- **Commands**: `copytrade:commands:{account_id}` — Connect/disconnect/subscribe commands

---

### 2. Windows VPS Services

#### Copy Engine (`backend/engine/`)

The copy engine is the core trade replication service.

**Master Listener** (`engine/master_listener.py`)
- One thread per master account
- Polls MT5 `positions_get()` every 10ms
- Detects: new positions (OPEN), closed positions (CLOSE), SL/TP changes (MODIFY)
- Also checks `history_deals_get()` for faster close detection
- Publishes `TradeEvent` to Redis pub/sub
- Target detection latency: <10ms

**Trade Distributor** (`engine/distributor.py`)
- Subscribes to `copytrade:events:*` Redis channels
- Looks up all connected clients for the master account (cached, 30s TTL)
- Calculates proportional lot sizes for each client
- Batch-enqueues `CopyOrder`s via Redis pipeline
- Target distribution latency: <5ms

**Lot Calculator** (`engine/lot_calculator.py`)
```
client_lots = master_lots × (client_balance / master_balance) × strategy_multiplier
```
Strategy multipliers:
| Level | Multiplier |
|-------|-----------|
| low | 0.5x |
| medium | 1.0x |
| high | 1.5x |
| pro | 2.0x |
| expert | 2.5x |
| expert_pro | 3.0x |

Lots are snapped to `lot_step` (default 0.01) and clamped to `[min_lot, max_lot]`.

**Executor** (`engine/executor.py`)
- Worker pool consuming from per-client Redis queues
- Executes MT5 `order_send()` for each CopyOrder
- Records result (ticket, price, latency) back to PostgreSQL
- Failed orders → dead letter queue with retry logic

#### MT5 Terminal Manager (`backend/mt5_manager/`)

Manages multiple MT5 terminal processes to support 2000+ accounts.

**Architecture**: Multi-account terminal pooling
- Each terminal process handles up to 50 accounts
- `TerminalPool` manages lifecycle of terminal processes
- `AccountSession` tracks individual account state within a terminal
- `AutoProvisioner` polls for new accounts to connect
- `Watchdog` monitors heartbeats and restarts stale terminals
- `BalanceSync` periodically updates account balances in DB
- `CredentialVault` handles encryption/decryption of MT5 passwords

**Scaling for 2000+ accounts**:
```
2000 accounts ÷ 50 per terminal = 40 terminal processes
Each terminal: ~512MB RAM → 40 × 512MB = ~20GB RAM
Recommended: 2-3 Windows VPS with 32GB RAM each
```

---

### 3. Communication Flow

#### Trade Copy Flow (end-to-end)
```
1. Master opens trade on MT5
2. MasterListener detects via positions_get() (<10ms)
3. TradeEvent published to Redis copytrade:events:{master_id}
4. Distributor receives event, looks up subscribed clients
5. Lot size calculated per client (proportional + strategy multiplier)
6. CopyOrder enqueued to copytrade:execute:{client_mt5_id}
7. Executor picks up order, calls MT5 order_send()
8. Result recorded to trade_copies table
9. If failed → dead_letter_trades for admin review/retry
```

#### User Connection Flow
```
1. User submits MT5 credentials via frontend
2. FastAPI encrypts password, stores in mt5_accounts
3. Redis command dispatched to MT5 Manager
4. MT5 Manager allocates terminal slot
5. Terminal connects to user's MT5 account
6. If user has active strategy → auto-subscribe to master's events
```

#### Ubuntu ↔ Windows Communication
- **Protocol**: Redis (pub/sub + list queues)
- **Security**: Redis AUTH + TLS, VPN tunnel between servers
- **Direction**: Bidirectional via Redis
  - Ubuntu → Windows: Connect/disconnect commands, strategy subscriptions
  - Windows → Ubuntu: Trade events, execution results, health status

---

### 4. Security

- **MT5 Passwords**: AES-256 encrypted at rest (`encrypt_mt5_password()` in `core/security.py`)
- **User Passwords**: bcrypt hashed
- **API Auth**: JWT tokens (access + refresh)
- **Admin Auth**: Role-based, admin flag on user model
- **Redis**: AUTH password + TLS in production
- **Inter-server**: VPN or mTLS between Ubuntu and Windows VPS

---

### 5. Deployment

#### Ubuntu Server (Docker Compose)
```bash
docker compose -f docker-compose.prod.yml up -d
# Services: api, postgres, redis, nginx
```

#### Windows VPS
```bash
# Install Python 3.11+, MetaTrader5 package
pip install -r requirements.txt -r requirements-mt5.txt

# Run Copy Engine
python -m engine.main

# Run MT5 Terminal Manager
python -m mt5_manager.main
```

Or via Docker (Windows containers):
```bash
docker compose -f docker-compose.mt5.yml up -d
```

#### Environment Variables (Windows VPS)
```env
DATABASE_URL_SYNC=postgresql://postgres:PASSWORD@UBUNTU_SERVER_IP:5432/copytrade
REDIS_URL=redis://:REDIS_PASSWORD@UBUNTU_SERVER_IP:6379/0
MT5_CREDENTIAL_KEY=your-32-byte-base64-key====
```

---

### 6. Testing Without Windows VPS

For local development without a Windows VPS:

1. **Mock MT5 Module**: Create a mock that simulates `MetaTrader5` API:
```python
# tests/mock_mt5.py
class MockMT5:
    def initialize(self): return True
    def login(self, login, password, server): return True
    def positions_get(self): return []
    def order_send(self, request): return MockResult(retcode=10009)
    def shutdown(self): pass
```

2. **Redis-only testing**: Run the distributor and executor with mock trade events published to Redis manually.

3. **Integration tests**: Use `pytest` with SQLAlchemy test fixtures and Redis mocking.

---

### 7. Monitoring

- **Grafana dashboards**: `monitoring/grafana/dashboards/`
- **Prometheus metrics**: Copy engine exposes latency, throughput, error rates
- **Loki logs**: Structured logging from all services
- **Health endpoints**: `/admin/operations` dashboard shows real-time status

---

### 8. Admin Strategy Management

The admin panel provides full CRUD for strategies and master accounts:

**Endpoints**:
- `GET /api/v1/admin/strategies` — List all strategies with master accounts
- `POST /api/v1/admin/strategies` — Create strategy (level, name, risk_multiplier)
- `PUT /api/v1/admin/strategies/{id}` — Update strategy
- `DELETE /api/v1/admin/strategies/{id}` — Delete strategy
- `POST /api/v1/admin/strategies/{id}/master-account` — Link/replace master account
- `PUT /api/v1/admin/strategies/{id}/master-account` — Update master account

**Frontend**: Admin Panel → "Strategies" tab with:
- Strategy cards showing level, multiplier, unlock status
- Master account details (login, server, balance)
- Create/Edit dialogs for strategies and master accounts
