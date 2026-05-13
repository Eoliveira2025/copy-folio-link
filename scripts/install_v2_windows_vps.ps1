<#
    install_v2_windows_vps.ps1
    Automated installation for CopyTrade Pro V2 on Institutional Windows VPS.
#>

$ErrorActionPreference = "Stop"

$V2_ROOT = "C:\copytrade_v2"
$V2_LOGS = "C:\copytrade_v2_logs"
$V2_POOL = "C:\MT5_Pool_V2"
$V2_MASTERS = "C:\MT5_Masters_V2"

Write-Host "--- CopyTrade Pro V2 Institutional Installation ---" -ForegroundColor Cyan

# 1. Create Directories
Write-Host "[1/5] Creating isolated directories..."
$dirs = @($V2_ROOT, $V2_LOGS, $V2_POOL, $V2_MASTERS)
foreach ($dir in $dirs) {
    if (!(Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir | Out-Null
        Write-Host " Created $dir"
    } else {
        Write-Host " Directory $dir already exists"
    }
}

# 2. Verify Python
Write-Host "[2/5] Verifying Python installation..."
try {
    $pyVersion = python --version
    Write-Host " Found $pyVersion"
} catch {
    Write-Error "Python not found. Please install Python 3.10+ and add it to PATH."
}

# 3. Setup Virtual Environment
Write-Host "[3/5] Setting up venv..."
Set-Location $V2_ROOT
if (!(Test-Path "venv")) {
    python -m venv venv
    Write-Host " venv created"
}

Write-Host " Installing dependencies..."
& ".\venv\Scripts\pip.exe" install --upgrade pip
if (Test-Path "requirements.txt") {
    & ".\venv\Scripts\pip.exe" install -r requirements.txt
} else {
    Write-Warning "requirements.txt not found in $V2_ROOT. Skipping pip install."
}

# 4. Environment Template
Write-Host "[4/5] Preparing environment file..."
if (!(Test-Path ".env")) {
    if (Test-Path "backend\agent_v2\.env.production.example") {
        Copy-Item "backend\agent_v2\.env.production.example" ".env"
        Write-Host " Created .env from example. PLEASE EDIT IT NOW."
    }
}

# 5. Check MT5
Write-Host "[5/5] Checking MetaTrader 5..."
$mt5Path = "C:\Program Files\MetaTrader 5\terminal64.exe"
if (Test-Path $mt5Path) {
    Write-Host " MT5 found at $mt5Path" -ForegroundColor Green
} else {
    Write-Warning "MT5 NOT found at $mt5Path. Please install it before running."
}

Write-Host "`n--- Installation Complete! ---" -ForegroundColor Green
Write-Host "Next steps:"
Write-Host "1. Edit C:\copytrade_v2\.env with your credentials."
Write-Host "2. Run scripts\start_v2_executor.ps1"
