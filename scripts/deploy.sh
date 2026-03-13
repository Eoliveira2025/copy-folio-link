#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# CopyTrade Pro — One-Command Production Deployment
# Usage: chmod +x deploy.sh && ./deploy.sh
# ═══════════════════════════════════════════════════════════════

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; exit 1; }
info() { echo -e "${CYAN}[i]${NC} $1"; }

echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
echo -e "${CYAN}   CopyTrade Pro — Production Deployment${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
echo ""

# ── Pre-flight checks ────────────────────────────────────
info "Running pre-flight checks..."

command -v docker >/dev/null 2>&1 || err "Docker is not installed. Install: https://docs.docker.com/engine/install/"
command -v docker compose >/dev/null 2>&1 || err "Docker Compose V2 is not installed."

if [ ! -f ".env" ]; then
    if [ -f ".env.production" ]; then
        warn ".env not found. Copying from .env.production..."
        cp .env.production .env
        warn "IMPORTANT: Edit .env with your real credentials before continuing!"
        echo ""
        read -p "Press Enter after editing .env, or Ctrl+C to abort..."
    else
        err ".env file not found. Copy .env.production to .env and fill in values."
    fi
fi

# Source env vars
set -a
source .env
set +a

# Validate required vars
[ -z "${DOMAIN:-}" ] && err "DOMAIN is not set in .env"
[ -z "${POSTGRES_PASSWORD:-}" ] && err "POSTGRES_PASSWORD is not set in .env"
[ -z "${SECRET_KEY:-}" ] && err "SECRET_KEY is not set in .env"
[ "${SECRET_KEY}" = "CHANGE-ME-use-openssl-rand-hex-64" ] && err "SECRET_KEY must be changed from default"

log "Pre-flight checks passed"

# ── Create directories ───────────────────────────────────
info "Creating directory structure..."
mkdir -p certbot/conf certbot/www nginx/conf.d
log "Directories created"

# ── Generate Nginx config from template ──────────────────
info "Generating Nginx configuration for ${DOMAIN}..."
envsubst '${DOMAIN}' < nginx/conf.d/default.conf.template > nginx/conf.d/default.conf
log "Nginx config generated"

# ── SSL Certificate Setup ────────────────────────────────
if [ ! -d "certbot/conf/live/${DOMAIN}" ]; then
    info "Obtaining SSL certificate for ${DOMAIN}..."

    # Start nginx with HTTP-only config for ACME challenge
    cat > nginx/conf.d/default.conf << 'HTTPEOF'
server {
    listen 80;
    server_name _;
    location /.well-known/acme-challenge/ { root /var/www/certbot; }
    location /health { return 200 '{"status":"ok"}'; add_header Content-Type application/json; }
    location / { return 301 https://$host$request_uri; }
}
HTTPEOF

    docker compose -f docker-compose.prod.yml up -d nginx
    sleep 5

    docker compose -f docker-compose.prod.yml run --rm certbot \
        certonly --webroot \
        --webroot-path=/var/www/certbot \
        --email "${SSL_EMAIL}" \
        --agree-tos --no-eff-email \
        -d "${DOMAIN}" -d "www.${DOMAIN}"

    docker compose -f docker-compose.prod.yml down nginx

    # Restore full config
    envsubst '${DOMAIN}' < nginx/conf.d/default.conf.template > nginx/conf.d/default.conf
    log "SSL certificate obtained"
else
    log "SSL certificate already exists"
fi

# ── Build & Start Services ───────────────────────────────
info "Building Docker images..."
docker compose -f docker-compose.prod.yml build --parallel
log "Images built"

info "Starting all services..."
docker compose -f docker-compose.prod.yml up -d
log "Services started"

# ── Wait for health ──────────────────────────────────────
info "Waiting for services to be healthy..."
sleep 10

MAX_RETRIES=30
RETRY=0
while [ $RETRY -lt $MAX_RETRIES ]; do
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        log "API is healthy"
        break
    fi
    RETRY=$((RETRY + 1))
    sleep 2
done

if [ $RETRY -eq $MAX_RETRIES ]; then
    warn "API did not become healthy within 60s. Check logs: docker compose -f docker-compose.prod.yml logs api"
fi

# ── Run database migrations ──────────────────────────────
info "Running database migrations..."
docker compose -f docker-compose.prod.yml exec api alembic upgrade head 2>/dev/null || warn "Migrations skipped (Alembic not configured yet)"

# ── Setup cron for backups ───────────────────────────────
info "Setting up daily backup cron..."
docker compose -f docker-compose.prod.yml exec db-backup sh -c \
    'echo "0 3 * * * /backup.sh >> /var/log/backup.log 2>&1" | crontab -' 2>/dev/null || warn "Backup cron setup skipped"

# ── Print Status ─────────────────────────────────────────
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}   Deployment Complete!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${CYAN}Frontend:${NC}    https://${DOMAIN}"
echo -e "  ${CYAN}API Docs:${NC}    https://${DOMAIN}/docs"
echo -e "  ${CYAN}Grafana:${NC}     https://${DOMAIN}/grafana/"
echo -e "  ${CYAN}API Health:${NC}  https://${DOMAIN}/health"
echo ""
echo -e "  ${YELLOW}Services Running:${NC}"
docker compose -f docker-compose.prod.yml ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || \
docker compose -f docker-compose.prod.yml ps
echo ""
echo -e "  ${YELLOW}Useful Commands:${NC}"
echo -e "    Logs:      docker compose -f docker-compose.prod.yml logs -f [service]"
echo -e "    Restart:   docker compose -f docker-compose.prod.yml restart [service]"
echo -e "    Stop:      docker compose -f docker-compose.prod.yml down"
echo -e "    Update:    git pull && ./deploy.sh"
echo -e "    Backup:    docker compose -f docker-compose.prod.yml exec db-backup /backup.sh"
echo ""
