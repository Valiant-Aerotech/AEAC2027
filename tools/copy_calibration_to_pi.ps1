# Copy validated calibration yaml back to Pi (bringup Phase C6)
param(
    [Parameter(Mandatory = $true)]
    [string]$PiHost,

    [string]$PiPath = "~/AEAC2027",
    [string]$LocalFile = "config\vion_calibration.yaml"
)
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$cal = Join-Path $RepoRoot $LocalFile

if (-not (Test-Path $cal)) {
    Write-Host "ERROR: $LocalFile not found. Run validate_calibration.py first." -ForegroundColor Red
    exit 1
}

Write-Host "Copying $LocalFile to Pi..."
scp $cal "${PiHost}:${PiPath}/config/vion_calibration.yaml"
Write-Host "OK. Pi ready for run_mission.py"
