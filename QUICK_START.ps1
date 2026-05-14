@echo off
setlocal enabledelayedexpansion

:: ── CopyTrade Pro V2 — Institutional Quick Start ──
:: This script prepares and starts the V2 environment on Windows VPS.

set "V2_ROOT=C:\copytrade-v2"
set "PYTHON_VER=3.12"

echo [1/6] Validating Directory Structure...
if not exist "%V2_ROOT%" (
    echo [ERROR] Root directory %V2_ROOT% not found.
    echo Please extract the ZIP to C:\copytrade-v2
    pause
    exit /b 1
)

cd /d "%V2_ROOT%"

:: Create essential folders
if not exist "logs" mkdir "logs"
if not exist "C:\copytrade_v2_logs" mkdir "C:\copytrade_v2_logs"
if not exist "C:\MT5_Pool_V2" mkdir "C:\MT5_Pool_V2"
if not exist "C:\MT5_Masters_V2" mkdir "C:\MT5_Masters_V2"

echo [2/6] Preparing Python Virtual Environment...
if not exist "venv" (
    echo Creating venv...
    python -m venv venv
)

echo [3/6] Installing Requirements...
call venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt

echo [4/6] Validating Configuration...
if not exist "backend\agent_v2\.env" (
    if exist "backend\agent_v2\.env.production.example" (
        echo [WARN] .env not found. Creating from example...
        copy "backend\agent_v2\.env.production.example" "backend\agent_v2\.env"
        echo [ACTION] Please edit backend\agent_v2\.env with your Redis/Postgres credentials.
    ) else (
        echo [ERROR] No .env or example found.
        pause
        exit /b 1
    )
)

echo [5/6] Validating MetaTrader 5...
:: Try to find MT5 in common paths if not configured
set "MT5_PATH=C:\Program Files\MetaTrader 5\terminal64.exe"
if not exist "%MT5_PATH%" (
    echo [WARN] MT5 not found at default path: %MT5_PATH%
    echo Please ensure MT5 is installed or update V2_MT5_TERMINAL_PATH in .env
)

echo [6/6] Launching Institutional V2...
echo Starting Executor Service...
start "V2_EXECUTOR" powershell -NoExit -ExecutionPolicy Bypass -File ".\scripts\start_v2_executor.ps1"

timeout /t 5

echo Starting Web Monitor...
:: The start_v2_executor.ps1 should ideally start both, but we ensure monitor is up
start "V2_MONITOR" powershell -NoExit -ExecutionPolicy Bypass -Command "cd C:\copytrade-v2; .\venv\Scripts\activate; python -m backend.agent_v2.monitor_app.server"

echo.
echo ── SETUP COMPLETE ──
echo Dashboard: http://localhost:8000
echo Health Check: Run .\scripts\health_check_v2.ps1
echo --------------------------------------------------
pause
