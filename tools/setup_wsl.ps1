# One-command WSL + ArduPilot SITL setup for a fresh Windows laptop.
# Usage (from repo root, Admin PowerShell if WSL is not installed yet):
#   .\tools\setup_wsl.ps1
#
# You do NOT clone this repo inside Ubuntu. Keep the repo on Windows (C:\...\AEAC2027).
# This script only clones ArduPilot inside WSL (public GitHub, no auth needed).
#
# After reboot (if WSL was just installed), run the same command again.
param(
    [switch]$SkipWslInstall
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot
. (Join-Path $PSScriptRoot "wsl_distro.ps1")

function Test-IsAdmin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

Write-Host ""
Write-Host "=== Valiant WSL + ArduPilot SITL setup ===" -ForegroundColor Cyan
Write-Host "Repo: $RepoRoot"
Write-Host ""

$distro = Get-ValiantWslDistro
if (-not (Test-ValiantWslReady)) {
    if ($SkipWslInstall) {
        Write-Host "ERROR: WSL Ubuntu not found. Install WSL first or re-run without -SkipWslInstall." -ForegroundColor Red
        Write-Host "Installed distros:" -ForegroundColor Yellow
        Get-WslDistroNames | ForEach-Object { Write-Host "  - $_" }
        exit 1
    }
    Write-Host "WSL Ubuntu not detected." -ForegroundColor Yellow
    $listed = Get-WslDistroNames
    if ($listed.Count -gt 0) {
        Write-Host "WSL distros seen: $($listed -join ', ')" -ForegroundColor DarkGray
        Write-Host "Open the Ubuntu app once from Start menu (finish Linux username/password)," -ForegroundColor Yellow
        Write-Host "then run this script again from PowerShell in the Windows repo folder." -ForegroundColor Yellow
        exit 1
    }
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

$distro = Get-ValiantWslDistro
Write-Host "Using WSL distro: $distro" -ForegroundColor Green

$ShWin = Join-Path $RepoRoot "tools\sitl\setup_wsl.sh"
if (-not (Test-Path $ShWin)) {
    Write-Error "Missing $ShWin"
}

Write-Host "Running ArduPilot setup inside WSL..." -ForegroundColor Yellow
Write-Host "(Repo stays on Windows; only ArduPilot clones in WSL ~/ardupilot.)" -ForegroundColor DarkGray
Write-Host "(First run: build can take 15-30 minutes.)" -ForegroundColor DarkGray
Write-Host ""

$ShForward = $ShWin -replace '\\', '/'
$WslScript = (wsl -d $distro wslpath -a $ShForward).Trim()
$code = Invoke-ValiantWsl -WslArgs @("bash", $WslScript)
if ($code -ne 0) {
    Write-Host ""
    Write-Host "WSL setup failed. See docs\runbooks\sitl-wsl.md" -ForegroundColor Red
    Write-Host ""
    Write-Host "Last build log (WSL):" -ForegroundColor Yellow
    wsl -d $distro bash -lc "tail -40 ~/.valiant_sitl_build.log 2>/dev/null || echo '(no build log yet - failure may be in prereqs step)'"
    Write-Host ""
    Write-Host "If prereqs already finished, retry build only:" -ForegroundColor Yellow
    Write-Host "  .\tools\setup_wsl.ps1"
    exit $code
}

Write-Host ""
Write-Host "Done. Start SITL:" -ForegroundColor Green
Write-Host "  Terminal 1:  .\tools\launch_sitl.ps1"
Write-Host "  Terminal 2:  python tools\valiant.py sitl mission"
Write-Host ""
