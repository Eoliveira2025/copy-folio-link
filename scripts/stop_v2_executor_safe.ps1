<#
    stop_v2_executor_safe.ps1
    Stops V2 processes safely without affecting V1.
#>

Write-Host "--- Stopping CopyTrade Pro V2 (Safe Mode) ---" -ForegroundColor Yellow

# 1. Kill Python processes running backend.agent_v2
Write-Host "Stopping V2 Python processes..."
Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*backend.agent_v2*" } | Stop-Process -Force

# 2. Optional: Signal MT5 terminals to close if they are in V2 pool
# (In a real production environment, we might want to wait for orders to finish)
Write-Host "V2 processes stopped." -ForegroundColor Green
