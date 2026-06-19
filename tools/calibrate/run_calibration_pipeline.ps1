# Full calibration pipeline: copy from Pi, validate, copy yaml back
param(
    [Parameter(Mandatory = $true)]
    [string]$PiHost,

    [string]$PiPath = "~/AEAC2027"
)
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "..\lib\script_paths.ps1")
$ctx = Initialize-ValiantScript -ScriptRoot $PSScriptRoot
$RepoRoot = $ctx.RepoRoot

Write-Host "=== Calibration pipeline ===" -ForegroundColor Cyan
& "$PSScriptRoot\copy_calibration_from_pi.ps1" -PiHost $PiHost -PiPath $PiPath
if ($LASTEXITCODE -ne 0) {
    Show-ValiantFailure "copy_calibration_from_pi failed" -Hints @(
        "Check PiHost and SSH",
        "Capture calibration on Pi first"
    )
}

Write-Host ""
Invoke-ValiantPythonStep -Label "Calibration validate (10% gate)" -Arguments @(
    "python", "tools\valiant.py", "calibrate", "validate"
) -Hints @(
    "Tune: python tools\valiant.py calibrate tune",
    "Re-capture on Pi and copy again"
)

& "$PSScriptRoot\copy_calibration_to_pi.ps1" -PiHost $PiHost -PiPath $PiPath
if ($LASTEXITCODE -ne 0) {
    Show-ValiantFailure "copy_calibration_to_pi failed" -Hints @("Check PiHost and SSH")
}
Write-Host "PASS: calibration on Pi" -ForegroundColor Green
