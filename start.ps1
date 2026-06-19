# First-time entry point for a new Windows laptop.
# Usage (from repo root): .\start.ps1
param(
    [switch]$SkipSetup
)

$ErrorActionPreference = "Stop"
$RepoRoot = $PSScriptRoot
Set-Location $RepoRoot

Write-Host ""
Write-Host "=== Valiant AEAC2027 — Start ===" -ForegroundColor Cyan
Write-Host "Repo: $RepoRoot"
Write-Host ""

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "ERROR: Python 3.10+ not found. Install from https://python.org and retry." -ForegroundColor Red
    exit 1
}

$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not $SkipSetup -and -not (Test-Path $VenvPython)) {
    Write-Host "No virtual environment found — running setup..." -ForegroundColor Yellow
    & "$RepoRoot\tools\setup.ps1"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

if (Test-Path $VenvPython) {
    $py = $VenvPython
} else {
    $py = "python"
}

Write-Host ""
Write-Host "Running quickstart checks..." -ForegroundColor Yellow
& $py tools\valiant.py quickstart
$code = $LASTEXITCODE

Write-Host ""
Write-Host "Read START_HERE.md for what to run next." -ForegroundColor Green
Write-Host "  python tools\valiant.py guide"
Write-Host ""

exit $code
