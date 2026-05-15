# V3 Patch Instructions - MetaApi SDK Fix

Este pacote contém a correção para o erro:
`MetaApi Error: 'MetaApi' object has no attribute 'provisioning_api'`

## O que mudou?
1. **client.py**: Atualizado para usar `metatrader_account_api` (compatível com SDK 29.1.1).
2. **service.py**: Adicionado suporte a `wait_until_connected` e atualização automática de status em background.
3. **requirements.v3.txt**: Fixado `metaapi-cloud-sdk==29.1.1`.

## Passo a Passo para aplicar no VPS 2 (Windows)

1. **Parar a API V3**:
   No PowerShell:
   ```powershell
   # Se estiver usando PM2 ou Processo Direto, pare-o
   # Exemplo se for uvicorn direto:
   Get-Process -Name "python" | Where-Object { $_.CommandLine -like "*8003*" } | Stop-Process -Force
   ```

2. **Substituir os arquivos**:
   Extraia os arquivos do ZIP para a pasta `backend/app` do seu projeto V3, substituindo os existentes.

3. **Atualizar Dependências**:
   No terminal da V3 (dentro do venv se usar):
   ```powershell
   pip install -r requirements.v3.txt
   ```

4. **Reiniciar a API V3**:
   ```powershell
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8003
   ```

5. **Testar**:
   Tente cadastrar uma nova conta MetaApi pelo Painel Admin. O erro de `provisioning_api` deve ter desaparecido.
