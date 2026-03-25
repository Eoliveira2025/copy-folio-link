#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# CopyTrade Pro — RESTAURAÇÃO COMPLETA DO SISTEMA
# Uso: chmod +x restore.sh && sudo ./restore.sh
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
echo -e "${CYAN}   CopyTrade Pro — RESTAURAÇÃO COMPLETA${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
echo ""

# ── PASSO 1: Parar e limpar tudo ─────────────────────────
info "Passo 1: Parando todos os containers..."
cd /root/copy-folio-link 2>/dev/null || cd /opt/copytrade 2>/dev/null || true

docker compose -f docker-compose.prod.yml down --remove-orphans 2>/dev/null || true
docker compose down --remove-orphans 2>/dev/null || true

# Parar TODOS os containers relacionados
docker ps -a --format '{{.Names}}' | grep '^ct-' | xargs -r docker rm -f 2>/dev/null || true

log "Containers parados e removidos"

# ── PASSO 2: Limpar imagens antigas ──────────────────────
info "Passo 2: Limpando imagens Docker antigas..."
docker system prune -f 2>/dev/null || true
log "Limpeza concluída"

# ── PASSO 3: Baixar versão estável do repositório ────────
info "Passo 3: Baixando versão estável do repositório..."

PROJECT_DIR="/root/copy-folio-link"

if [ -d "$PROJECT_DIR" ]; then
    cd "$PROJECT_DIR"
    # Salvar .env se existir
    [ -f .env ] && cp .env /tmp/.env.backup 2>/dev/null || true
    
    git fetch origin main
    git reset --hard origin/main
    git clean -fd
    log "Repositório atualizado para última versão estável"
else
    cd /root
    git clone https://github.com/Eoliveira2025/copy-folio-link.git
    cd copy-folio-link
    log "Repositório clonado"
fi

PROJECT_DIR="$(pwd)"

# ── PASSO 4: Criar .env correto ──────────────────────────
info "Passo 4: Configurando .env com banco externo..."

cat > "$PROJECT_DIR/.env" << 'ENVEOF'
# ═══════════════════════════════════════════════════════════
# CopyTrade Pro — Configuração de Produção
# ═══════════════════════════════════════════════════════════

# ── Domain ────────────────────────────────────────────────
DOMAIN=91.98.20.163

# ── Application ───────────────────────────────────────────
APP_NAME=CopyTrade Pro API
DEBUG=false
API_PREFIX=/api/v1
ENVIRONMENT=production
SECRET_KEY=copytrade-prod-secret-key-2025-change-later

# ── PostgreSQL (banco externo) ────────────────────────────
POSTGRES_DB=copytrade
POSTGRES_USER=copytrade
POSTGRES_PASSWORD=admin123

# Conexões usadas pela API (apontam para o banco externo)
DATABASE_URL=postgresql+asyncpg://copytrade:admin123@91.98.20.163:5432/copytrade
DATABASE_URL_SYNC=postgresql://copytrade:admin123@91.98.20.163:5432/copytrade

# ── Redis (container local, sem senha) ────────────────────
REDIS_URL=redis://redis:6379/0

# ── JWT ───────────────────────────────────────────────────
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=30

# ── MT5 Credential Encryption ────────────────────────────
MT5_CREDENTIAL_KEY=change-me-32-byte-base64-key====

# ── CORS ──────────────────────────────────────────────────
ALLOWED_ORIGINS=http://91.98.20.163,http://91.98.20.163:8080,http://91.98.20.163:8000,http://localhost:5173

# ── Subscription ─────────────────────────────────────────
FREE_TRIAL_DAYS=30
SUBSCRIPTION_PRICE=49.90
SUBSCRIPTION_CURRENCY=BRL

# ── Rate Limiting ────────────────────────────────────────
LOGIN_RATE_LIMIT=10
LOGIN_RATE_WINDOW=300

# ── Frontend URL ─────────────────────────────────────────
FRONTEND_URL=http://91.98.20.163

# ── Asaas ─────────────────────────────────────────────────
ASAAS_ENABLED=false
ASAAS_API_KEY=
ASAAS_SANDBOX=true
ENVEOF

log ".env configurado com banco externo"

# ── PASSO 5: Criar docker-compose simplificado ───────────
# Usamos o docker-compose.prod.yml do repo mas sem o banco
# local (usamos banco externo) e sem Redis password
info "Passo 5: Preparando docker-compose..."

# O docker-compose.prod.yml já está no repo atualizado
# Mas precisamos de um override para usar banco externo
cat > "$PROJECT_DIR/docker-compose.override.yml" << 'OVERRIDEEOF'
version: "3.9"

# Override para usar banco PostgreSQL externo
# (remove o serviço db local do docker-compose.prod.yml)
services:
  api:
    environment:
      - DATABASE_URL=postgresql+asyncpg://copytrade:admin123@91.98.20.163:5432/copytrade
      - DATABASE_URL_SYNC=postgresql://copytrade:admin123@91.98.20.163:5432/copytrade
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      redis:
        condition: service_healthy

  celery-worker:
    environment:
      - DATABASE_URL_SYNC=postgresql://copytrade:admin123@91.98.20.163:5432/copytrade
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      redis:
        condition: service_healthy

  celery-beat:
    environment:
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      redis:
        condition: service_healthy
OVERRIDEEOF

log "docker-compose override criado"

# ── PASSO 6: Build das imagens ───────────────────────────
info "Passo 6: Construindo imagens Docker..."
docker compose -f docker-compose.prod.yml build api 2>&1 | tail -5
log "Imagens construídas"

# ── PASSO 7: Iniciar serviços ────────────────────────────
info "Passo 7: Iniciando serviços..."

# Iniciar Redis primeiro
docker compose -f docker-compose.prod.yml up -d redis
sleep 3

# Verificar Redis
if docker exec ct-redis redis-cli ping 2>/dev/null | grep -q PONG; then
    log "Redis OK"
else
    warn "Redis pode demorar, continuando..."
fi

# Iniciar API
docker compose -f docker-compose.prod.yml up -d api
sleep 5

# Iniciar Celery
docker compose -f docker-compose.prod.yml up -d celery-worker celery-beat
sleep 2

# Iniciar Nginx
docker compose -f docker-compose.prod.yml up -d nginx
sleep 3

log "Serviços iniciados"

# ── PASSO 8: Aguardar API ficar saudável ─────────────────
info "Passo 8: Aguardando API ficar saudável..."

MAX_RETRIES=30
RETRY=0
API_OK=false
while [ $RETRY -lt $MAX_RETRIES ]; do
    if docker exec ct-api curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        API_OK=true
        break
    fi
    RETRY=$((RETRY + 1))
    sleep 2
done

if [ "$API_OK" = true ]; then
    log "API está saudável!"
else
    warn "API não respondeu em 60s. Verificando logs..."
    docker logs ct-api --tail 20
    echo ""
    warn "Tente: docker logs ct-api --tail 50"
fi

# ── PASSO 9: Executar migrations ─────────────────────────
info "Passo 9: Executando migrations do banco..."
docker exec ct-api alembic upgrade head 2>&1 || warn "Migrations podem já estar aplicadas"
log "Migrations executadas"

# ── PASSO 10: Iniciar frontend ───────────────────────────
info "Passo 10: Iniciando frontend..."

# Verificar se npm/node está instalado no host
if command -v npm >/dev/null 2>&1; then
    cd "$PROJECT_DIR"
    
    # Instalar deps se necessário
    [ -d node_modules ] || npm install
    
    # Matar processo anterior do Vite
    pkill -f "vite" 2>/dev/null || true
    sleep 1
    
    # Iniciar frontend em background
    VITE_API_URL=http://91.98.20.163:8000 nohup npx vite --host 0.0.0.0 --port 8080 > /tmp/frontend.log 2>&1 &
    sleep 3
    
    if curl -sf http://localhost:8080 > /dev/null 2>&1; then
        log "Frontend rodando na porta 8080"
    else
        warn "Frontend pode demorar para iniciar. Verifique: cat /tmp/frontend.log"
    fi
else
    warn "npm não encontrado. Instale Node.js ou rode o frontend manualmente:"
    echo "    cd $PROJECT_DIR && npm install && VITE_API_URL=http://91.98.20.163:8000 npx vite --host 0.0.0.0 --port 8080"
fi

# ── PASSO 11: Configurar Nginx (se não está no Docker) ───
info "Passo 11: Verificando Nginx..."

# Se o nginx do docker não funcionar, configurar nginx do host
if ! docker exec ct-nginx nginx -t 2>/dev/null; then
    if command -v nginx >/dev/null 2>&1; then
        cat > /etc/nginx/sites-available/copytrade << 'NGINXEOF'
server {
    listen 80;
    server_name 91.98.20.163;

    # Frontend
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # API
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # API Health
    location /health {
        proxy_pass http://127.0.0.1:8000;
    }

    # API Docs
    location /docs {
        proxy_pass http://127.0.0.1:8000;
    }

    location /redoc {
        proxy_pass http://127.0.0.1:8000;
    }

    location /openapi.json {
        proxy_pass http://127.0.0.1:8000;
    }
}
NGINXEOF
        ln -sf /etc/nginx/sites-available/copytrade /etc/nginx/sites-enabled/copytrade 2>/dev/null || true
        rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true
        nginx -t && systemctl reload nginx
        log "Nginx do host configurado"
    else
        warn "Nginx não encontrado no host"
    fi
else
    log "Nginx Docker OK"
fi

# ── RESULTADO FINAL ──────────────────────────────────────
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}   RESTAURAÇÃO CONCLUÍDA!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${CYAN}Verificações:${NC}"
echo ""

# Verificar cada serviço
echo -n "  Redis:     "
docker exec ct-redis redis-cli ping 2>/dev/null && echo "" || echo -e "${RED}FALHOU${NC}"

echo -n "  API:       "
curl -sf http://localhost:8000/health 2>/dev/null && echo "" || echo -e "${RED}FALHOU${NC}"

echo -n "  Frontend:  "
curl -sf http://localhost:8080 > /dev/null 2>&1 && echo -e "${GREEN}OK${NC}" || echo -e "${RED}FALHOU${NC}"

echo -n "  Nginx:     "
curl -sf http://localhost:80 > /dev/null 2>&1 && echo -e "${GREEN}OK${NC}" || echo -e "${YELLOW}Via Docker${NC}"

echo ""
echo -e "  ${CYAN}URLs:${NC}"
echo -e "    Frontend:        http://91.98.20.163"
echo -e "    API Health:      http://91.98.20.163:8000/health"
echo -e "    API Docs:        http://91.98.20.163:8000/docs"
echo -e "    Provisionamento: http://91.98.20.163/admin/provisioning"
echo ""
echo -e "  ${YELLOW}Comandos úteis:${NC}"
echo -e "    Logs API:      docker logs ct-api --tail 50 -f"
echo -e "    Logs Frontend: cat /tmp/frontend.log"
echo -e "    Reiniciar API: docker restart ct-api"
echo -e "    Status:        docker ps --format 'table {{.Names}}\t{{.Status}}'"
echo ""
