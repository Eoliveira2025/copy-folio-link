# Guia de Deploy V3 MetaApi - VPS 2 (Homologação)

Este guia foi feito para quem não é técnico. Siga os passos com calma.

## 1. Instalar Dependências
No seu VPS 2, abra o terminal (PowerShell ou Bash) e execute:

```bash
# Atualizar repositórios
sudo apt update && sudo apt upgrade -y

# Instalar Docker e Docker Compose (se não tiver)
sudo apt install docker.io docker-compose -y

# Entrar na pasta do projeto
cd /home/usuario/copytrade-pro/backend

# Instalar as bibliotecas Python necessárias
pip install -r requirements.txt
```

## 2. Configurar o arquivo .env
Crie um arquivo chamado `.env.v3` na pasta `backend`:

```bash
nano .env.v3
```

Cole o conteúdo abaixo e substitua `SEU_TOKEN_AQUI` pelo token que você pegou no site da MetaApi:

```env
METAAPI_TOKEN=SEU_TOKEN_AQUI
METAAPI_ENABLED=true
COPYFACTORY_ENABLED=true
ENVIRONMENT=homologation
V3_FEATURE_FLAG=true
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/copytrade_v3
```
*Pressione Ctrl+O, Enter e Ctrl+X para salvar.*

## 3. Rodar Migrations (Banco de Dados)
Isso cria as tabelas da V3 sem apagar nada da V1.

```bash
# Executar a migração específica da V3
alembic upgrade 019_add_metaapi_v3
```

## 4. Subir os Containers
```bash
# Subir apenas os serviços da V3
docker-compose up -d --build
```

## 5. Testar Health Check (Ver se está vivo)
Abra no seu navegador ou use o comando:

```bash
curl http://localhost:8000/api/v1/metaapi/health
```
Deve retornar: `{"status": "ready", "version": "v3-metaapi"}`

## 6. Conectar Conta Master Demo
1. Acesse o Painel Admin.
2. Vá em **Contas Cloud (V3)** -> **Novo Master**.
3. Preencha: Login MT5, Senha, Servidor da Corretora.
4. Clique em **Provisionar**. Aguarde ficar "CONNECTED".

## 7. Conectar Conta Cliente Demo
1. Vá em **Usuários** -> Selecione um usuário de teste.
2. Clique em **Adicionar Conta Cloud**.
3. Preencha os dados da conta demo do cliente.

## 8. Testar uma Cópia de Ordem
1. Abra o MetaTrader 5 na conta Master.
2. Abra uma ordem de COMPRA (BUY) 0.01 em qualquer par (ex: EURUSD).
3. Verifique no Painel V3 se a ordem apareceu em "Eventos Recentes".
4. Verifique se a conta Cliente abriu a mesma ordem automaticamente.

## 9. Como Voltar Atrás (Rollback)
Se algo der errado e você quiser desligar a V3:

1. No arquivo `.env.v3`, mude:
   `V3_FEATURE_FLAG=false`
2. Reinicie o sistema:
   `docker-compose restart`

Para remover as tabelas da V3 (Cuidado!):
```bash
alembic downgrade 018_v2_symbol_map
```

---
**Importante:** A V1 continua rodando nos containers originais. A V3 está isolada pela flag `V3_FEATURE_FLAG`.
