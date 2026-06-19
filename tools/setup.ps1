# Valiant Aerotech - one-time setup for a fresh Windows GCS laptop
# Usage: .\tools\setup.ps1

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

function Get-NormalizedPath {
    param([string]$Path)
    return [System.IO.Path]::GetFullPath($Path).TrimEnd('\').ToLowerInvariant()
}

function Test-VenvHealthy {
    param(
        [string]$RepoRootPath,
        [string]$VenvPython
    )

    if (-not (Test-Path $VenvPython)) {
        return $false
    }

    $pyvenvCfg = Join-Path $RepoRootPath ".venv\pyvenv.cfg"
    if (-not (Test-Path $pyvenvCfg)) {
        return $false
    }

    $expectedVenv = Get-NormalizedPath (Join-Path $RepoRootPath ".venv")
    $cfgContent = Get-Content $pyvenvCfg -Raw
    if ($cfgContent -match "command\s*=\s*.*-m venv\s+(.+)") {
        $createdPath = Get-NormalizedPath $Matches[1].Trim()
        if ($createdPath -ne $expectedVenv) {
            Write-Host "Stale virtual environment detected." -ForegroundColor Yellow
            Write-Host "  Created at: $($Matches[1].Trim())"
            Write-Host "  Expected:   $(Join-Path $RepoRootPath '.venv')"
            return $false
        }
    }

    & $VenvPython -m pip --version 2>$null | Out-Null
    return $LASTEXITCODE -eq 0
}

function Invoke-VenvPip {
    param(
        [string]$VenvPython,
        [string[]]$PipArguments
    )

    & $VenvPython -m pip @PipArguments
    if ($LASTEXITCODE -ne 0) {
        throw "pip failed with exit code $LASTEXITCODE"
    }
}

Write-Host "=== AEAC2027 Setup ===" -ForegroundColor Cyan
Write-Host "Repo: $RepoRoot"

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "ERROR: Python not found. Install Python 3.10+ and add to PATH." -ForegroundColor Red
    exit 1
}
Write-Host "Python: $(python --version)"

$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$venvHealthy = Test-VenvHealthy -RepoRootPath $RepoRoot -VenvPython $VenvPython

if (-not $venvHealthy) {
    if (Test-Path ".venv") {
        Write-Host "Removing broken virtual environment..."
        Remove-Item -Recurse -Force ".venv"
    }
    Write-Host "Creating virtual environment..."
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to create virtual environment." -ForegroundColor Red
        exit 1
    }
    $VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
}

Write-Host "Activating .venv..."
& "$RepoRoot\.venv\Scripts\Activate.ps1"

Write-Host "Installing dependencies..."
Invoke-VenvPip -VenvPython $VenvPython -PipArguments @("install", "--upgrade", "pip")
Invoke-VenvPip -VenvPython $VenvPython -PipArguments @("install", "-e", ".[gcs,cv,dev]", "-r", "requirements.txt")

Write-Host ""
Write-Host "Setup complete. Next steps:" -ForegroundColor Green
Write-Host "  python tools\valiant.py quickstart"
Write-Host "  python tools\valiant.py guide"
Write-Host "  notepad config\vion.yaml"
Write-Host ""
Write-Host "Full walkthrough: START_HERE.md"
