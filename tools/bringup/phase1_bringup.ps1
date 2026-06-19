# Phase 1 - GCS link + actuation (field-test-plan.md section 1)
# Usage: .\tools\bringup\phase1_bringup.ps1 [-SkipMavlink]
param(
    [switch]$SkipMavlink
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "..\lib\script_paths.ps1")
$ctx = Initialize-ValiantScript -ScriptRoot $PSScriptRoot
$RepoRoot = $ctx.RepoRoot

Write-Host "=== Phase 1 bringup (GCS + tethered prep) ===" -ForegroundColor Cyan
Write-Host ""

Invoke-ValiantPythonStep -Label "Environment" -Arguments @("python", "tools\valiant.py", "env", "check") -Hints @(
    "Run: .\tools\setup.ps1"
)
Invoke-ValiantPythonStep -Label "CONOPS config" -Arguments @("python", "tools\valiant.py", "conops", "check") -Hints @(
    "Edit config\rpas.yaml"
)
Invoke-ValiantPythonStep -Label "Safety logic" -Arguments @("python", "tools\valiant.py", "bench", "safety")

if (-not $SkipMavlink) {
    Write-Host ""
    $hbRc = Invoke-ValiantPythonStep -Label "MAVLink heartbeat" -Arguments @(
        "python", "tools\valiant.py", "gcs", "heartbeat"
    ) -AllowFail -Hints @(
        "Set config/rpas.yaml mavlink.connection to your radio COM port",
        "Re-run with -SkipMavlink for laptop-only checks"
    )
    if ($hbRc -ne 0) {
        Write-ValiantWarn "Heartbeat failed - fix COM port or use -SkipMavlink"
    }
} else {
    Write-Host ""
    Write-Host "MAVLink heartbeat skipped (-SkipMavlink)" -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "Manual Phase 1 (drone + Pi):" -ForegroundColor Yellow
Write-Host "  - Mission Planner at 57600, GUIDED_NOGPS for indoor"
Write-Host "  - python tools\valiant.py gcs spray  (SERVO15, props off)"
Write-Host "  - bash hardware/vion/rpi/phase1_bringup.sh  (on Pi)"
Write-Host ""
Write-Host "See docs\runbooks\field-test-plan.md Phase 1"
