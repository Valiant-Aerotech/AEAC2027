# Phase 1 - GCS link + actuation (field-test-plan.md section 1)
# Usage: .\tools\phase1_bringup.ps1 [-SkipMavlink]
param(
    [switch]$SkipMavlink
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

Write-Host "=== Phase 1 bringup (GCS + tethered prep) ===" -ForegroundColor Cyan
Write-Host ""

Write-Host "1. Environment..." -ForegroundColor Yellow
python tools\valiant.py env check
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "2. CONOPS config..." -ForegroundColor Yellow
python tools\valiant.py conops check
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "3. Safety logic..." -ForegroundColor Yellow
python tools\valiant.py bench safety
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (-not $SkipMavlink) {
    Write-Host ""
    Write-Host "4. MAVLink heartbeat (drone powered, radio on COM)..." -ForegroundColor Yellow
    python tools\valiant.py gcs heartbeat
    if ($LASTEXITCODE -ne 0) {
        Write-Host "WARN: heartbeat failed - set config/vion.yaml mavlink.connection and retry." -ForegroundColor Yellow
        Write-Host "       Or re-run with -SkipMavlink for laptop-only checks." -ForegroundColor Yellow
    }
} else {
    Write-Host ""
    Write-Host "4. MAVLink heartbeat skipped (-SkipMavlink)" -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "Manual Phase 1 (drone + Pi):" -ForegroundColor Yellow
Write-Host "  - Mission Planner at 57600, GUIDED_NOGPS for indoor"
Write-Host "  - python tools\valiant.py gcs spray  (SERVO15, props off)"
Write-Host "  - bash hardware/vion/rpi/phase1_bringup.sh  (on Pi)"
Write-Host "  - python tools\valiant.py gcs monitor  (optional)"
Write-Host ""
Write-Host "See docs\runbooks\field-test-plan.md Phase 1"
