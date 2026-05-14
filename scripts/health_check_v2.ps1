<#
    health_check_v2.ps1
    Verifies if V2 processes and connectivity are healthy.
#>

$V2_ROOT = "C:\copytrade-v2"
Set-Location $V2_ROOT

Write-Host "--- V2 Institutional Status Report ---" -ForegroundColor Cyan

# 1. Check Executor Process
$executor = Get-CimInstance Win32_Process -Filter "Name = 'python.exe' AND CommandLine LIKE '%backend.agent_v2.main%'"
if ($executor) {
    Write-Host "[OK] V2 Executor is running (PID: $($executor.ProcessId))" -ForegroundColor Green
} else {
    Write-Host "[FAIL] V2 Executor is NOT running" -ForegroundColor Red
}

# 2. Check Monitor Process
$monitor = Get-CimInstance Win32_Process -Filter "Name = 'python.exe' AND CommandLine LIKE '%backend.agent_v2.monitor_app.server%'"
if ($monitor) {
    Write-Host "[OK] V2 Monitor Web Server is running (PID: $($monitor.ProcessId))" -ForegroundColor Green
} else {
    Write-Host "[FAIL] V2 Monitor Web Server is NOT running" -ForegroundColor Red
}

# 3. Check Web API Response
try {
    $res = Invoke-RestMethod -Uri "http://localhost:8000/health" -Method Get -TimeoutSec 2
    if ($res.status -eq "healthy") {
        Write-Host "[OK] V2 Monitor API responding" -ForegroundColor Green
    }
} catch {
    Write-Host "[FAIL] V2 Monitor API NOT responding (Port 8000)" -ForegroundColor Red
}

# 4. Run Technical Pre-flight
Write-Host "Running pre-flight connectivity test..." -ForegroundColor Gray
& ".\venv\Scripts\python.exe" -m backend.agent_v2.tests.run_final_v2_preflight --short

