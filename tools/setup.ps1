# Valiant Aerotech - one-time setup for a fresh Windows GCS laptop
# Usage: .\tools\setup.ps1

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

Write-Host "=== AEAC2027 Setup ===" -ForegroundColor Cyan
Write-Host "Repo: $RepoRoot"

# Python check
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "ERROR: Python not found. Install Python 3.10+ and add to PATH." -ForegroundColor Red
    exit 1
}
Write-Host "Python: $(python --version)"

# Virtual environment (optional but recommended)
if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
}
Write-Host "Activating .venv..."
& "$RepoRoot\.venv\Scripts\Activate.ps1"

# Install package in editable mode + all deps
Write-Host "Installing dependencies..."
pip install --upgrade pip
pip install -e ".[gcs,cv,dev]" -r requirements.txt

Write-Host ""
Write-Host "Setup complete. Next steps:" -ForegroundColor Green
Write-Host "  python tools\verify_env.py"
Write-Host "  notepad config\vion.yaml"
Write-Host "  python missions\task2_vion_manual_photo.py"
