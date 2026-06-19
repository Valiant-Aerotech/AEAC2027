# Copy validated calibration yaml back to Pi (bringup Phase C6)
param(
    [Parameter(Mandatory = $true)]
    [string]$PiHost,

    [string]$PiPath = "~/AEAC2027",
    [string]$LocalFile = "config\vion_calibration.yaml"
)
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "..\lib\script_paths.ps1")
$ctx = Initialize-ValiantScript -ScriptRoot $PSScriptRoot
$RepoRoot = $ctx.RepoRoot
$cal = Join-Path $RepoRoot $LocalFile

if (-not (Test-Path $cal)) {
    Write-Host "ERROR: $LocalFile not found. Run valiant calibrate validate first." -ForegroundColor Red
    exit 1
}

Write-Host "Copying $LocalFile to Pi..."
scp $cal "${PiHost}:${PiPath}/config/vion_calibration.yaml"
Write-Host "OK. Pi ready for run_mission.py"
