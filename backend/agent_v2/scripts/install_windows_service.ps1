# Install CopyTradeProV2 as a Windows service (NSSM-based).
# Requires NSSM (https://nssm.cc/) and a python.exe in PATH.
# Service name is intentionally distinct from V1 (CopyTradeProV1).

$ErrorActionPreference = "Stop"
$serviceName = "CopyTradeProV2"
$python = (Get-Command python.exe).Source
$workDir = (Resolve-Path "$PSScriptRoot\..\..").Path

if (-not (Get-Command nssm -ErrorAction SilentlyContinue)) {
    throw "NSSM not found. Install from https://nssm.cc/ first."
}

nssm install   $serviceName $python "-m" "agent_v2.main"
nssm set       $serviceName AppDirectory $workDir
nssm set       $serviceName AppStdout    "C:\copytrade_v2_logs\service.out.log"
nssm set       $serviceName AppStderr    "C:\copytrade_v2_logs\service.err.log"
nssm set       $serviceName Start        SERVICE_AUTO_START
# Safe defaults
nssm set       $serviceName AppEnvironmentExtra `
    "V2_EXECUTION_MODE=DRY_RUN" `
    "V2_ORDER_EXECUTION_ENABLED=false" `
    "V2_SESSION_DRY_RUN=true" `
    "V2_CLOSE_RECONCILER_ENABLED=false"

Write-Host "Installed service '$serviceName'. Start with: nssm start $serviceName"
