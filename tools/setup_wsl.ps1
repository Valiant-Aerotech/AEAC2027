# One-command WSL + ArduPilot SITL setup for a fresh Windows laptop.
# Usage (from repo root, Admin PowerShell if WSL is not installed yet):
#   .\tools\setup_wsl.ps1
param(
    [switch]$SkipWslInstall
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "wsl_distro.ps1")
$RepoRoot = Get-ValiantRepoRoot -FromScriptRoot $PSScriptRoot
Set-Location $RepoRoot
. (Join-Path $PSScriptRoot "lib\diagnostics.ps1")

function Test-IsAdmin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

Write-Host ""
Write-Host "=== Valiant WSL + ArduPilot SITL setup ===" -ForegroundColor Cyan
Write-Host "Repo: $RepoRoot"
Write-Host ""

if (-not (Test-ValiantWslReady)) {
    if ($SkipWslInstall) {
        Show-ValiantFailure "WSL Ubuntu not found" -Hints @(
            "Install WSL or re-run without -SkipWslInstall"
        ) -Doc "docs\runbooks\sitl-wsl.md"
    }
    Write-Host "WSL Ubuntu not detected." -ForegroundColor Yellow
    $listed = Get-WslDistroNames
    if ($listed.Count -gt 0) {
        Write-Host "WSL distros seen: $($listed -join ', ')" -ForegroundColor DarkGray
        Show-ValiantFailure "Ubuntu not initialized" -Hints @(
            "Open Ubuntu from Start menu (finish Linux username/password)",
            "Then re-run: .\tools\setup_wsl.ps1"
        ) -Doc "docs\runbooks\sitl-wsl.md"
    }
    if (-not (Test-IsAdmin)) {
        Write-Host ""
        Write-Host "Run ONCE in Administrator PowerShell:" -ForegroundColor Yellow
        Write-Host "  wsl --install -d Ubuntu"
        Write-Host ""
        Write-Host "Then reboot, open Ubuntu once, and run:" -ForegroundColor Yellow
        Write-Host "  .\tools\setup_wsl.ps1"
        Write-Host ""
        exit 1
    }
    Write-Host "Installing WSL + Ubuntu (may require a reboot)..." -ForegroundColor Yellow
    wsl --install -d Ubuntu --no-launch
    Write-Host ""
    Write-Host "If Windows asks you to reboot, do that first." -ForegroundColor Green
    Write-Host "After reboot: open Ubuntu, finish user setup, run: .\tools\setup_wsl.ps1" -ForegroundColor Green
    Write-Host ""
    exit 0
}

$distro = Get-ValiantWslDistro
Write-Host "Using WSL distro: $distro" -ForegroundColor Green

$ShWin = Get-ValiantRepoPath -RelativePath "sitl\setup_wsl.sh" -FromScriptRoot $PSScriptRoot
Write-Host "Running ArduPilot setup inside WSL..." -ForegroundColor Yellow
Write-Host "(First run: build can take 15-30 minutes.)" -ForegroundColor DarkGray
Write-Host ""

Invoke-ValiantWslBashScript `
    -WinScriptPath $ShWin `
    -LogFile "~/.valiant_sitl_setup.log" `
    -FailureContext "WSL SITL setup failed" `
    -TreatSitlBuiltAsSuccess `
    -Hints @(
        "If prereqs finished, re-run: .\tools\setup_wsl.ps1",
        "Manual: source ~/venv-ardupilot/bin/activate; cd ~/ardupilot; ./waf copter -j4"
    ) | Out-Null

Write-Host ""
Write-Host "Done. Start SITL:" -ForegroundColor Green
Write-Host "  Terminal 1:  .\tools\launch_sitl.ps1"
Write-Host "  Terminal 2:  python tools\valiant.py sitl mission"
Write-Host ""
