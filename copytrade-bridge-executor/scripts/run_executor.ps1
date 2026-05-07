Param()

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
& "$root\.venv\Scripts\Activate.ps1"
Set-Location $root
python -m app.main
