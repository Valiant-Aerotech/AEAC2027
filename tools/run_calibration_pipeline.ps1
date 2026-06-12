# Full calibration pipeline: copy from Pi, validate, copy yaml back
param(
    [Parameter(Mandatory = $true)]
    [string]$PiHost,

    [string]$PiPath = "~/AEAC2027"
)
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

Write-Host "=== Calibration pipeline ===" -ForegroundColor Cyan
& "$PSScriptRoot\copy_calibration_from_pi.ps1" -PiHost $PiHost -PiPath $PiPath

Write-Host ""
Write-Host "Validating (10% gate)..." -ForegroundColor Yellow
python tools\validate_calibration.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "FAIL: tune with tools\calibrate_depth_rgb.py and re-capture on Pi" -ForegroundColor Red
    exit 1
}

& "$PSScriptRoot\copy_calibration_to_pi.ps1" -PiHost $PiHost -PiPath $PiPath
Write-Host "PASS: calibration on Pi" -ForegroundColor Green
