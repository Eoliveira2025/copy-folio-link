<#
    health_check_v2.ps1
    Checks if V2 processes and connectivity are healthy.
#>

$V2_ROOT = "C:\copytrade-v2"
Set-Location $V2_ROOT

Write-Host "--- V2 Institutional Health Check ---" -ForegroundColor Cyan

# 1. Check Process
$proc = Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*backend.agent_v2*" }
if ($proc) {
    Write-Host "[OK] V2 Master Monitor is running (PID: $($proc.Id))" -ForegroundColor Green
} else {
    Write-Host "[FAIL] V2 Master Monitor is NOT running" -ForegroundColor Red
}

# 2. Run Pre-flight Connectivity Test
Write-Host "Running connectivity tests..."
& ".\venv\Scripts\python.exe" backend\agent_v2\tests\run_final_v2_preflight.py --short
