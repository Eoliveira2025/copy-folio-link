# CopyTrade Pro V2 — Windows stop script
# Targets only the V2 process; never touches V1 (CopyTradeProV1).

$ErrorActionPreference = "SilentlyContinue"

Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like "*agent_v2.main*" } |
    ForEach-Object {
        Write-Host "Stopping V2 PID=$($_.ProcessId)"
        Stop-Process -Id $_.ProcessId -Force
    }
