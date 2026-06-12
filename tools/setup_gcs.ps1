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
Write-Host "GCS dev commands:"
Write-Host "  python tools\metric_bench_test.py --camera 0"
Write-Host "  python tools\replay_rpi_recording.py --recording-dir logs\calibration"
Write-Host "  python tools\validate_calibration.py"
Write-Host "  python tools\mission_monitor.py"
