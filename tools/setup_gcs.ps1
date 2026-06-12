# GCS development setup (calibration, monitor, replay - no FC required)
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

Write-Host "=== AEAC2027 GCS setup ===" -ForegroundColor Cyan
& "$PSScriptRoot\setup.ps1"

if (-not (Test-Path "config\vion_calibration.yaml")) {
    Copy-Item "config\vion_calibration.yaml.example" "config\vion_calibration.yaml"
    Write-Host "Created config\vion_calibration.yaml from example"
}

Write-Host ""
Write-Host "GCS bringup (first drone connect):" -ForegroundColor Cyan
Write-Host "  .\tools\bringup_gcs.ps1"
Write-Host ""
Write-Host "GCS dev commands:" -ForegroundColor Cyan
Write-Host "  python tools\mission_monitor.py"
Write-Host "  python tools\validate_calibration.py"
Write-Host "  python tools\replay_rpi_recording.py --recording-dir logs\calibration"
Write-Host ""
Write-Host "Docs: docs\runbooks\vion-bringup.md"
