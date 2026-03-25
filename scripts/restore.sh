#!/bin/bash
# ═══════════════════════════════════════════════════════════
# CopyTrade Pro — Full System Restoration Script
# Run on Ubuntu server as root: chmod +x restore.sh && sudo ./restore.sh
# ═══════════════════════════════════════════════════════════
set -e

echo "═══════════════════════════════════════════════════"
echo "  CopyTrade Pro — System Restoration"
echo "═══════════════════════════════════════════════════"

# ── Configuration ──────────────────────────────────────
PROJECT_DIR="/opt/copytrade"
REPO_URL="https://github.com/Eoliveira2025/copy-folio-link.git"
BRANCH="main"

DB_HOST="91.98.20.163"
DB_PORT="5432"
DB_NAME="copytrade"
DB_USER="copytrade"
DB_PASS="admin123"

ADMIN_EMAIL="admin@copytrade.com"
ADMIN_PASSWORD='admin123.0@'

MT5_FERNET_KEY="-RK0mmmLcWul2UvY9jAc9NqMYopVvoWfYmHk9-iDbkk="
ASAAS_API_KEY='$aact_hmlg_000MzkwODA2MWY2OGM3MWRlMDU2NWM3MzJlNzZmNGZhZGY6OjZhZDRlNTcwLTNhODctNGM1My04NTc3LWEyODIxYWYyM2YzNzo6JGFhY2hfZWYwMTg0YjYtZmU2OC00YzBmLWI5MjYtZDcwNTA5ZWRlMWU5'
ASAAS_WEBHOOK_SECRET="whsec_U-ZKBpN_1JOzWRInmQSECg6XOueFmZnMo7tDNhwMJYM"

SERVER_IP="91.98.20.163"
SECRET_KEY=$(openssl rand -hex 32 2>/dev/null || echo "change-me-use-openssl-rand-hex-64")

# ── Step 1: Survey current state ──────────────────────
echo ""
echo "▶ Step 1: Surveying current state..."
echo "  Docker containers:"
docker ps -a --format "  {{.Names}} | {{.Status}}" 2>/dev/null || echo "  No Docker"
echo "  Project directory: $(ls -d $PROJECT_DIR 2>/dev/null || echo 'NOT FOUND')"

# ── Step 2: Stop existing services ────────────────────
echo ""
echo "▶ Step 2: Stopping existing services..."
cd "$PROJECT_DIR" 2>/dev/null && docker compose down --remove-orphans 2>/dev/null || true
cd "$PROJECT_DIR" 2>/dev/null && docker compose -f docker-compose.prod.yml down --remove-orphans 2>/dev/null || true
cd "$PROJECT_DIR" 2>/dev/null && docker compose -f docker-compose.restore.yml down --remove-orphans 2>/dev/null || true
docker stop ct-api-new ct-api ct-redis ct-nginx ct-celery 2>/dev/null || true
docker rm ct-api-new ct-api ct-redis ct-nginx ct-celery 2>/dev/null || true

# Kill stray processes on ports
fuser -k 8000/tcp 2>/dev/null || true
fuser -k 8080/tcp 2>/dev/null || true

# ── Step 3: Pull latest code ──────────────────────────
echo ""
echo "▶ Step 3: Pulling latest code..."
mkdir -p "$PROJECT_DIR"
cd "$PROJECT_DIR"

if [ -d ".git" ]; then
    git fetch origin
    git reset --hard origin/$BRANCH
    git clean -fd
else
    cd /opt
    rm -rf copytrade
    git clone -b $BRANCH $REPO_URL copytrade
    cd "$PROJECT_DIR"
fi

# ── Step 4: Create .env ───────────────────────────────
echo ""
echo "▶ Step 4: Creating .env..."
cat > "$PROJECT_DIR/backend/.env" << ENVEOF
APP_NAME=CopyTrade Pro API
DEBUG=false
API_PREFIX=/api/v1
ENVIRONMENT=production

DATABASE_URL=postgresql+asyncpg://${DB_USER}:${DB_PASS}@${DB_HOST}:${DB_PORT}/${DB_NAME}
DATABASE_URL_SYNC=postgresql://${DB_USER}:${DB_PASS}@${DB_HOST}:${DB_PORT}/${DB_NAME}

SECRET_KEY=${SECRET_KEY}
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=30

REDIS_URL=redis://ct-redis:6379/0

MT5_CREDENTIAL_KEY=${MT5_FERNET_KEY}

ASAAS_ENABLED=true
ASAAS_API_KEY=${ASAAS_API_KEY}
ASAAS_ENVIRONMENT=sandbox
ASAAS_SANDBOX=true
ASAAS_WEBHOOK_TOKEN=${ASAAS_WEBHOOK_SECRET}
ASAAS_WEBHOOK_ENABLED=true
ASAAS_TIMEOUT_SECONDS=30
ASAAS_BILLING_DUE_DAYS=1

FREE_TRIAL_DAYS=30
INVOICE_GENERATE_BEFORE_DAYS=10
INVOICE_DUE_AFTER_DAYS=2
BLOCK_AFTER_OVERDUE_DAYS=2
SUBSCRIPTION_PRICE=49.90
SUBSCRIPTION_CURRENCY=BRL

LOGIN_RATE_LIMIT=10
LOGIN_RATE_WINDOW=300

ALLOWED_ORIGINS=http://${SERVER_IP},http://${SERVER_IP}:8080,http://${SERVER_IP}:8000

FRONTEND_URL=http://${SERVER_IP}
ENVEOF

echo "  .env created"

# ── Step 5: Build and start containers ────────────────
echo ""
echo "▶ Step 5: Building and starting containers..."

cat > "$PROJECT_DIR/docker-compose.restore.yml" << 'DCEOF'
version: "3.8"
services:
  ct-redis:
    image: redis:7-alpine
    container_name: ct-redis
    restart: unless-stopped
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3
    networks:
      - copytrade

  ct-api:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: ct-api-new
    restart: unless-stopped
    ports:
      - "8000:8000"
    env_file:
      - ./backend/.env
    depends_on:
      ct-redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost:8000/health"]
      interval: 15s
      timeout: 5s
      retries: 5
    networks:
      - copytrade

networks:
  copytrade:
    name: copytrade_net
    driver: bridge
DCEOF

cd "$PROJECT_DIR"
docker compose -f docker-compose.restore.yml build --no-cache ct-api
docker compose -f docker-compose.restore.yml up -d

echo "  Waiting for API to be ready..."
for i in $(seq 1 30); do
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        echo "  ✓ API is healthy"
        break
    fi
    sleep 2
done

# ── Step 6: Run migrations ────────────────────────────
echo ""
echo "▶ Step 6: Running database migrations..."
docker exec ct-api-new python -m alembic upgrade head 2>&1 || echo "  ⚠ Migration warning (may be OK if tables exist)"

# ── Step 7: Build frontend ────────────────────────────
echo ""
echo "▶ Step 7: Building frontend..."
cd "$PROJECT_DIR"

cat > ".env" << FENVEOF
VITE_API_URL=http://${SERVER_IP}/api/v1
FENVEOF

if command -v bun &>/dev/null; then
    bun install --frozen-lockfile 2>/dev/null || bun install
    bun run build
elif command -v npm &>/dev/null; then
    npm ci 2>/dev/null || npm install
    npm run build
fi

mkdir -p /opt/copytrade/dist
cp -r dist/* /opt/copytrade/dist/ 2>/dev/null || true

# ── Step 8: Configure Nginx ───────────────────────────
echo ""
echo "▶ Step 8: Configuring Nginx..."

cat > /etc/nginx/sites-available/copytrade << 'NGXEOF'
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
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 30s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    location /health {
        proxy_pass http://127.0.0.1:8000;
    }

    location /docs {
        proxy_pass http://127.0.0.1:8000;
    }
    location /redoc {
        proxy_pass http://127.0.0.1:8000;
    }
    location /openapi.json {
        proxy_pass http://127.0.0.1:8000;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
NGXEOF

ln -sf /etc/nginx/sites-available/copytrade /etc/nginx/sites-enabled/copytrade
rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true
nginx -t && systemctl reload nginx

# ── Step 9: Health checks ─────────────────────────────
echo ""
echo "▶ Step 9: Running health checks..."
echo ""

if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
    echo "  ✓ API: healthy"
else
    echo "  ✗ API: FAILED"
fi

if curl -sf http://localhost/ > /dev/null 2>&1; then
    echo "  ✓ Nginx: serving frontend"
else
    echo "  ✗ Nginx: FAILED"
fi

if curl -sf http://localhost/health > /dev/null 2>&1; then
    echo "  ✓ Nginx → API proxy: working"
else
    echo "  ✗ Nginx → API proxy: FAILED"
fi

if docker exec ct-redis redis-cli ping 2>/dev/null | grep -q PONG; then
    echo "  ✓ Redis: PONG"
else
    echo "  ✗ Redis: FAILED"
fi

LOGIN_RESULT=$(curl -sf -X POST http://localhost:8000/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"${ADMIN_EMAIL}\",\"password\":\"${ADMIN_PASSWORD}\"}" 2>/dev/null || echo "FAILED")

if echo "$LOGIN_RESULT" | grep -q access_token; then
    echo "  ✓ Admin login: working"
else
    echo "  ⚠ Admin login: restart API once to auto-create admin"
    docker restart ct-api-new
    sleep 5
    LOGIN_RESULT=$(curl -sf -X POST http://localhost:8000/api/v1/auth/login \
        -H "Content-Type: application/json" \
        -d "{\"email\":\"${ADMIN_EMAIL}\",\"password\":\"${ADMIN_PASSWORD}\"}" 2>/dev/null || echo "FAILED")
    if echo "$LOGIN_RESULT" | grep -q access_token; then
        echo "  ✓ Admin login: working (after restart)"
    else
        echo "  ✗ Admin login: FAILED — check logs: docker logs ct-api-new"
    fi
fi

echo ""
echo "═══════════════════════════════════════════════════"
echo "  Restoration complete!"
echo ""
echo "  Frontend: http://${SERVER_IP}"
echo "  API:      http://${SERVER_IP}/api/v1"
echo "  Docs:     http://${SERVER_IP}/docs"
echo "  Admin:    ${ADMIN_EMAIL}"
echo "═══════════════════════════════════════════════════"
