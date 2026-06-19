# Task 2 webcam bench smoke test (no drone, no scrcpy)
# Usage: .\tools\bench\webcam_bench.ps1

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "..\lib\script_paths.ps1")
$ctx = Initialize-ValiantScript -ScriptRoot $PSScriptRoot
$RepoRoot = $ctx.RepoRoot

$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (Test-Path $VenvPython) {
    $python = $VenvPython
} else {
    $python = "python"
}

Write-Host "=== AEAC2027 Webcam Bench ===" -ForegroundColor Cyan
Write-Host "Tip: python tools\valiant.py guide  lists all scenarios"
Write-Host ""

Write-Host "[1/1] valiant quickstart" -ForegroundColor Yellow
& $python tools\valiant.py quickstart
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "Interactive (hold purple target in center box):" -ForegroundColor Cyan
Write-Host "  python tools\valiant.py bench cv --camera 0"
Write-Host "  python tools\valiant.py bench metric --camera 0"
