# Start GCS mission monitor for Pi telemetry mirror (Phase D)
param(
    [string]$Connection = $null
)
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

Write-Host "=== GCS mission monitor ===" -ForegroundColor Cyan
Write-Host "Ensure Pi runs run_mission.py with:"
Write-Host "  --gcs-connection udpout:<THIS_LAPTOP_IP>:14550"
Write-Host ""
Write-Host "Ctrl+C to stop."
Write-Host ""

if ($Connection) {
    python tools\mission_monitor.py --connection $Connection
} else {
    python tools\mission_monitor.py
}
