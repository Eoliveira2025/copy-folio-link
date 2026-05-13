# CopyTrade Pro V2 — Windows start script (separate from V1)
# Usage:
#   .\start_v2.ps1
# Defaults are SAFE: DRY_RUN, no real order_send, dry-run sessions.

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot\..

$env:V2_EXECUTION_MODE          = if ($env:V2_EXECUTION_MODE)          { $env:V2_EXECUTION_MODE }          else { "DRY_RUN" }
$env:V2_ORDER_EXECUTION_ENABLED = if ($env:V2_ORDER_EXECUTION_ENABLED) { $env:V2_ORDER_EXECUTION_ENABLED } else { "false" }
$env:V2_SESSION_DRY_RUN         = if ($env:V2_SESSION_DRY_RUN)         { $env:V2_SESSION_DRY_RUN }         else { "true" }
$env:V2_CLOSE_RECONCILER_ENABLED = if ($env:V2_CLOSE_RECONCILER_ENABLED) { $env:V2_CLOSE_RECONCILER_ENABLED } else { "false" }

Write-Host "Starting CopyTradeProV2 (mode=$($env:V2_EXECUTION_MODE), order_send=$($env:V2_ORDER_EXECUTION_ENABLED))"
python -m agent_v2.main
