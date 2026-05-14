<#
    start_v2_executor.ps1
    Starts the CopyTrade Pro V2 Institutional Executor.
#>

$V2_ROOT = "C:\copytrade-v2"
Set-Location $V2_ROOT

Write-Host "--- Starting CopyTrade Pro V2 Institutional ---" -ForegroundColor Cyan

if (!(Test-Path ".env")) {
    Write-Error "Configuration file (.env) not found in $V2_ROOT"
    exit 1
}

# Activate venv and run main
Write-Host "Launching V2 Master Monitor..."
& ".\venv\Scripts\python.exe" -m backend.agent_v2.main
