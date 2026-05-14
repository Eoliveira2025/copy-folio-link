<#
    start_v2_executor.ps1
    Starts the CopyTrade Pro V2 Institutional Executor with Watchdog and Monitor.
#>

$V2_ROOT = "C:\copytrade-v2"
$LOG_DIR = "$V2_ROOT\logs"
if (!(Test-Path $LOG_DIR)) { New-Item -ItemType Directory $LOG_DIR }

Set-Location $V2_ROOT

Write-Host "--- CopyTrade Pro V2 Institutional Bootloader ---" -ForegroundColor Cyan

# Check for .env in current dir first, then in backend/agent_v2
if (Test-Path "backend\agent_v2\.env") {
    $ENV_FILE = "backend\agent_v2\.env"
} elseif (Test-Path ".env") {
    $ENV_FILE = ".env"
} else {
    Write-Error "Configuration file (.env) not found. Please create backend\agent_v2\.env"
    exit 1
}

# 1. Start Monitor Web Server
Write-Host "Launching V2 Monitor Server..."
$monitorProc = Start-Process ".\venv\Scripts\python.exe" -ArgumentList "-m uvicorn backend.agent_v2.monitor_app.server:app --host 0.0.0.0 --port 8000" -WindowStyle Minimized -PassThru -RedirectStandardOutput "$LOG_DIR\v2_monitor.log" -RedirectStandardError "$LOG_DIR\v2_monitor_error.log"

# 2. Main Executor Loop (Watchdog)
Write-Host "Starting V2 Executor Watchdog..." -ForegroundColor Green

while ($true) {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp] Launching V2 Executor..." -ForegroundColor Gray
    
    $executor = Start-Process ".\venv\Scripts\python.exe" -ArgumentList "-m backend.agent_v2.main" -NoNewWindow -PassThru -Wait -RedirectStandardOutput "$LOG_DIR\v2_executor.log" -RedirectStandardError "$LOG_DIR\v2_executor_error.log"
    
    $exitCode = $executor.ExitCode
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    
    if ($exitCode -eq 0) {
        Write-Host "[$timestamp] Executor stopped gracefully (Exit 0). Stopping watchdog." -ForegroundColor Yellow
        break
    } else {
        Write-Host "[$timestamp] Executor CRASHED with Exit Code $exitCode. Restarting in 5s..." -ForegroundColor Red
        Add-Content -Path "$LOG_DIR\v2_watchdog.log" -Value "[$timestamp] CRASH detected. Exit Code: $exitCode. Restarting..."
        Start-Sleep -Seconds 5
    }
}

# Cleanup monitor if executor stops gracefully
if ($monitorProc) { Stop-Process $monitorProc.Id -ErrorAction SilentlyContinue }

