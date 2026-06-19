# Task 2 webcam bench smoke test (no drone, no scrcpy)
# Usage: .\tools\webcam_bench.ps1

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (Test-Path $VenvPython) {
    $python = $VenvPython
} else {
    $python = "python"
}

Write-Host "=== AEAC2027 Webcam Bench ===" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1/3] valiant env check" -ForegroundColor Yellow
& $python tools\valiant.py env check
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "[2/3] valiant conops check" -ForegroundColor Yellow
& $python tools\valiant.py conops check
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "[3/3] valiant bench safety" -ForegroundColor Yellow
& $python tools\valiant.py bench safety
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "Interactive steps (hold purple target in center 224x224 box):" -ForegroundColor Cyan
Write-Host "  python tools\valiant.py bench cv --camera 0"
Write-Host "  python tools\valiant.py bench metric --camera 0"
Write-Host "  python missions\task2_vion_manual_photo.py --camera 0"
Write-Host "  python missions\task2_vion_auto_extinguish.py --sim --source webcam --camera 0 --max-targets 1"
