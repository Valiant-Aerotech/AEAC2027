# One-command WSL + ArduPilot SITL setup for a fresh Windows laptop.
# Usage (from repo root, Admin PowerShell if WSL is not installed yet):
#   .\tools\setup_wsl.ps1
#
# After reboot (if WSL was just installed), run the same command again.
param(
    [switch]$SkipWslInstall
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

function Test-IsAdmin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Test-WslAvailable {
    try {
        $out = wsl -l -v 2>&1
        if ($LASTEXITCODE -ne 0) { return $false }
        return ($out -match "Ubuntu")
    }
    catch {
        return $false
    }
}

Write-Host ""
Write-Host "=== Valiant WSL + ArduPilot SITL setup ===" -ForegroundColor Cyan
Write-Host "Repo: $RepoRoot"
Write-Host ""

if (-not (Test-WslAvailable)) {
    if ($SkipWslInstall) {
        Write-Host "ERROR: WSL Ubuntu not found. Install WSL first or re-run without -SkipWslInstall." -ForegroundColor Red
        exit 1
    }
    Write-Host "WSL Ubuntu not detected." -ForegroundColor Yellow
    if (-not (Test-IsAdmin)) {
        Write-Host ""
        Write-Host "Run ONCE in an Administrator PowerShell:" -ForegroundColor Yellow
        Write-Host "  wsl --install -d Ubuntu"
        Write-Host ""
        Write-Host "Then reboot, open Ubuntu once to create your Linux user," -ForegroundColor Yellow
        Write-Host "and run this script again from the repo:" -ForegroundColor Yellow
        Write-Host "  .\tools\setup_wsl.ps1"
        Write-Host ""
        exit 1
    }
    Write-Host "Installing WSL + Ubuntu (may require a reboot)..." -ForegroundColor Yellow
    wsl --install -d Ubuntu --no-launch
    Write-Host ""
    Write-Host "If Windows asks you to reboot, do that first." -ForegroundColor Green
    Write-Host "After reboot: open Ubuntu from Start menu, finish user setup," -ForegroundColor Green
    Write-Host "then run again:  .\tools\setup_wsl.ps1" -ForegroundColor Green
    Write-Host ""
    exit 0
}

$ShWin = Join-Path $RepoRoot "tools\sitl\setup_wsl.sh"
if (-not (Test-Path $ShWin)) {
    Write-Error "Missing $ShWin"
}

Write-Host "WSL Ubuntu OK. Running ArduPilot setup inside WSL..." -ForegroundColor Yellow
Write-Host "(First run: clone + build can take 15-30 minutes.)" -ForegroundColor DarkGray
Write-Host ""

$ShForward = $ShWin -replace '\\', '/'
$WslScript = (wsl wslpath -a $ShForward).Trim()
wsl bash $WslScript
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "WSL setup failed. See docs\runbooks\sitl-wsl.md" -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "Done. Start SITL:" -ForegroundColor Green
Write-Host "  Terminal 1:  .\tools\launch_sitl.ps1"
Write-Host "  Terminal 2:  python tools\valiant.py sitl mission"
Write-Host ""
