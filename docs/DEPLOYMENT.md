# ═══════════════════════════════════════════════════════════════
# CopyTrade Pro — Production Deployment Guide
# ═══════════════════════════════════════════════════════════════

## Prerequisites

- VPS with Ubuntu 22.04+ (minimum 8GB RAM, 4 vCPUs, 100GB SSD)
- Domain name pointed to VPS IP
- Docker and Docker Compose V2 installed

## Quick Start (One Command)

```bash
# 1. Clone the repository
git clone https://github.com/your-org/copytrade-pro.git
cd copytrade-pro

# 2. Copy and configure environment
cp .env.production .env
nano .env   # Fill in all CHANGE-ME values

# 3. Deploy everything
chmod +x scripts/deploy.sh
./scripts/deploy.sh
```

## Environment Setup

### Generate Required Keys

```bash
# Secret key for JWT
openssl rand -hex 64

# Fernet key for MT5 password encryption
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Redis password
openssl rand -hex 32

# PostgreSQL password
openssl rand -hex 32

# Grafana password
openssl rand -hex 16
```

### Required DNS Records

| Type | Name | Value |
|------|------|-------|
| A    | @    | YOUR_VPS_IP |
| A    | www  | YOUR_VPS_IP |

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    NGINX (SSL)                       │
│                 Port 80/443                           │
└────────────┬────────────┬────────────┬──────────────┘
             │            │            │
     ┌───────▼───┐  ┌─────▼─────┐  ┌──▼──────────┐
     │  Frontend │  │  API      │  │  Grafana    │
     │  Static   │  │  :8000    │  │  :3000      │
     └───────────┘  └─────┬─────┘  └─────────────┘
                          │
              ┌───────────┼───────────┐
              │           │           │
     ┌────────▼──┐  ┌─────▼────┐  ┌──▼──────────┐
     │ PostgreSQL│  │  Redis   │  │ Copy Engine  │
     │  :5432    │  │  :6379   │  │             │
     └───────────┘  └──────────┘  └──────┬──────┘
                                         │
                                  ┌──────▼──────┐
                                  │ MT5 Manager │
                                  │ (Wine+Xvfb) │
                                  └─────────────┘
```

## Services

| Service | Description | Port |
|---------|-------------|------|
| nginx | Reverse proxy + SSL | 80, 443 |
| api | FastAPI application | 8000 (internal) |
| copy-engine | Trade copy distributor | — |
| mt5-manager | MT5 terminal pool | — |
| celery-worker | Background task processor | — |
| celery-beat | Scheduled task scheduler | — |
| db | PostgreSQL 16 | 5432 (internal) |
| redis | Redis 7 message broker | 6379 (internal) |
| prometheus | Metrics collection | 9090 (internal) |
| grafana | Monitoring dashboards | 3000 (internal) |
| loki | Log aggregation | 3100 (internal) |
| promtail | Log shipping | — |
| node-exporter | System metrics | 9100 (internal) |
| certbot | SSL renewal | — |
| db-backup | Daily PostgreSQL backups | — |

## Monitoring

- **Grafana**: `https://yourdomain.com/grafana/`
- Default login: `admin` / your GRAFANA_PASSWORD
- Pre-configured datasources: Prometheus + Loki

### Key Metrics
- API response times and error rates
- PostgreSQL connection pool usage
- Redis memory and hit rate
- System CPU, memory, disk usage
- Copy engine latency and trade execution rate

## Maintenance

### View Logs
```bash
# All services
docker compose -f docker-compose.prod.yml logs -f

# Specific service
docker compose -f docker-compose.prod.yml logs -f api
docker compose -f docker-compose.prod.yml logs -f copy-engine
docker compose -f docker-compose.prod.yml logs -f mt5-manager
```

### Manual Backup
```bash
docker compose -f docker-compose.prod.yml exec db-backup /backup.sh
```

### Restore Backup
```bash
gunzip < backups/copytrade_YYYYMMDD_HHMMSS.sql.gz | \
  docker compose -f docker-compose.prod.yml exec -T db psql -U copytrade_user copytrade
```

### Update Deployment
```bash
git pull
./scripts/deploy.sh
```

### SSL Certificate Renewal
Automatic via certbot container every 12 hours. Manual:
```bash
docker compose -f docker-compose.prod.yml run --rm certbot renew
docker compose -f docker-compose.prod.yml exec nginx nginx -s reload
```

### Scale MT5 Manager
For more than 500 concurrent terminals, add more MT5 manager instances:
```bash
docker compose -f docker-compose.prod.yml up -d --scale mt5-manager=3
```

## Security Checklist

- [ ] Change all `CHANGE-ME` values in `.env`
- [ ] Use strong, unique passwords (32+ chars)
- [ ] Restrict SSH to key-based auth only
- [ ] Enable UFW firewall (allow 80, 443, SSH only)
- [ ] Set up fail2ban for SSH protection
- [ ] Review CORS origins in API (change from `*`)
- [ ] Enable Stripe webhook signature verification
- [ ] Set up VPS monitoring alerts
- [ ] Test backup restore procedure

## Firewall Setup
```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

## Troubleshooting

### Service won't start
```bash
docker compose -f docker-compose.prod.yml logs [service]
```

### Database connection refused
```bash
docker compose -f docker-compose.prod.yml exec db pg_isready
```

### Redis connection issues
```bash
docker compose -f docker-compose.prod.yml exec redis redis-cli -a $REDIS_PASSWORD ping
```

### SSL not working
```bash
docker compose -f docker-compose.prod.yml logs certbot
# Check DNS propagation at https://dnschecker.org
```
