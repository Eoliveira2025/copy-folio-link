param (
    [string]$Token = ""
)

if ($Token -eq "") {
    # Tentar ler do .env se não passado
    if (Test-Path ".env.v3") {
        $tokenLine = Get-Content ".env.v3" | Select-String "METAAPI_TOKEN"
        if ($tokenLine) {
            $Token = $tokenLine.ToString().Split("=")[1].Trim()
        }
    }
}

if ($Token -eq "") {
    Write-Error "Token MetaApi não fornecido e não encontrado no .env.v3"
    exit
}

Write-Host "Testando Conexão MetaApi..." -ForegroundColor Cyan

$pythonCode = @"
import asyncio
from metaapi_cloud_sdk import MetaApi

async def test():
    token = '$Token'
    api = MetaApi(token)
    try:
        provisioning_api = api.provisioning_api
        accounts = await provisioning_api.get_accounts()
        print(f'SUCCESS: Conectado com sucesso. {len(accounts)} contas encontradas.')
    except Exception as e:
        print(f'ERROR: Falha na conexão: {e}')

asyncio.run(test())
"@

$pythonCode | python -

Write-Host "Teste concluído."
