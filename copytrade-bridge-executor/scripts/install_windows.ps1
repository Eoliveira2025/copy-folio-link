Param()

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")

Write-Host "==> Creating venv at $root\.venv"
python -m venv "$root\.venv"

Write-Host "==> Installing requirements"
& "$root\.venv\Scripts\python.exe" -m pip install --upgrade pip
& "$root\.venv\Scripts\python.exe" -m pip install -r "$root\requirements.txt"

if (-not (Test-Path "$root\.env")) {
    Copy-Item "$root\.env.example" "$root\.env"
    Write-Host "==> .env created from .env.example. Edit it before running."
} else {
    Write-Host "==> .env already exists, leaving it untouched."
}

Write-Host "==> Done. Next: edit .env and run scripts\run_executor.ps1"
