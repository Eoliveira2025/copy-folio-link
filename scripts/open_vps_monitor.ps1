<#
    open_vps_monitor.ps1
    Starts the monitor server if needed and opens the dashboard.
#>

$port = 8000
$V2_ROOT = "C:\copytrade-v2"

# Check if port is already listening
$isOpen = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue

if (!$isOpen) {
    Write-Host "V2 Monitor server not running. Starting it..." -ForegroundColor Yellow
    Start-Process "powershell.exe" -ArgumentList "-NoExit", "-Command", "cd $V2_ROOT; .\venv\Scripts\python.exe -m uvicorn backend.agent_v2.monitor_app.server:app --host 0.0.0.0 --port $port" -WindowStyle Minimized
    
    # Wait a bit for server to start
    Start-Sleep -Seconds 2
}

Write-Host "Opening V2 local monitor at http://localhost:$port" -ForegroundColor Cyan
Start-Process "http://localhost:$port"
