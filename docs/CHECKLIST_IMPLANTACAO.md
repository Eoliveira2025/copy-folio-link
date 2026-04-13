# CopyTrade Pro — Checklist de Implantação

> Passos rápidos para colocar o sistema em produção.

---

## Pré-requisitos

- [ ] Ubuntu 22.04 LTS com acesso root
- [ ] Docker + Docker Compose V2 instalados
- [ ] Domínio apontando para o IP do servidor (registro A)
- [ ] Porta 80 e 443 abertas no firewall
- [ ] Windows VPS separado para MT5 (se trading ativo)

## Configuração

- [ ] Clonar repositório: `git clone <repo> /opt/copytrade`
- [ ] Copiar `.env.production` para `.env`
- [ ] Definir `DOMAIN` com seu domínio
- [ ] Gerar `SECRET_KEY`: `openssl rand -hex 64`
- [ ] Definir `POSTGRES_PASSWORD` (senha forte)
- [ ] Definir `GRAFANA_PASSWORD`
- [ ] Configurar `ASAAS_API_KEY` (sandbox ou produção)
- [ ] Gerar `MT5_CREDENTIAL_KEY`: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`

## Deploy

- [ ] Executar `./scripts/deploy.sh`
- [ ] Aguardar certificado SSL ser emitido
- [ ] Verificar health: `curl https://seudominio.com/health`

## Pós-Deploy

- [ ] Acessar `https://seudominio.com`
- [ ] Login com admin padrão (`admin@copytrade.com` / `admin123.0@`)
- [ ] **Alterar senha do admin imediatamente**
- [ ] Criar planos de assinatura via Admin Panel
- [ ] Criar/ativar termos de uso via Admin Panel
- [ ] Configurar estratégias de trading
- [ ] Verificar Grafana: `https://seudominio.com/grafana/`
- [ ] Verificar backup automático: `docker compose -f docker-compose.prod.yml exec db-backup ls /backups/`

## Windows VPS (MT5)

- [ ] Instalar Python 3.12 no Windows VPS
- [ ] Copiar pasta `backend/agent/` para o VPS
- [ ] Copiar `backend/agent/.env.example` para `.env`
- [ ] Configurar `DATABASE_URL_SYNC` e `REDIS_URL` apontando para o Ubuntu
- [ ] Configurar `MT5_CREDENTIAL_KEY` (mesma chave do Ubuntu)
- [ ] Instalar MetaTrader 5 e configurar contas-mestre
- [ ] Executar: `pip install -r requirements-agent.txt && python -m agent.main`

## Validação Final

- [ ] Login funciona
- [ ] Cadastro funciona (com CPF/CNPJ)
- [ ] Modal de termos aparece e aceite persiste
- [ ] Conexão MT5 funciona (se VPS configurado)
- [ ] Checkout e pagamento funcionam (sandbox)
- [ ] Painel admin acessível
- [ ] Grafana exibe métricas
- [ ] Backup diário configurado
- [ ] SSL válido (verificar em https://www.ssllabs.com)
