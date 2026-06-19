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

Write-Host "[1/4] verify_env.py" -ForegroundColor Yellow
& $python tools\verify_env.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "[2/4] conops_check.py" -ForegroundColor Yellow
& $python tools\conops_check.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "[3/4] safety_bench_test.py" -ForegroundColor Yellow
& $python tools\safety_bench_test.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "[4/4] Automated checks done." -ForegroundColor Green
Write-Host ""
Write-Host "Interactive steps (hold purple target in center 224x224 box):" -ForegroundColor Cyan
Write-Host "  python tools\yolo_webcam_test.py --camera 0"
Write-Host "  python tools\valiant.py bench cv --camera 0"
Write-Host "  python tools\valiant.py bench metric --camera 0"
Write-Host "  python missions\task2_vion_manual_photo.py --camera 0"
Write-Host "  python missions\task2_vion_auto_extinguish.py --sim --source webcam --camera 0 --max-targets 1"
