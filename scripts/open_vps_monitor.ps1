<#
    open_vps_monitor.ps1
    Opens the local V2 Institutional Monitor Dashboard.
#>

$port = 8000 # Default V2 monitor port
Write-Host "Opening V2 local monitor at http://localhost:$port" -ForegroundColor Cyan
Start-Process "http://localhost:$port"
