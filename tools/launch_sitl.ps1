$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ShWin = Join-Path $Root "tools\sitl\launch_sitl.sh"
. (Join-Path $PSScriptRoot "lib\diagnostics.ps1")

Write-Host "Starting ArduPilot SITL in WSL..."
Write-Host "Requires ~/ardupilot in WSL - run .\tools\setup_wsl.ps1 if not built yet"
Write-Host "Companion connects: tcp:127.0.0.1:5760 (no MAVProxy required)"
Write-Host ""

Invoke-ValiantWslBashScript `
    -WinScriptPath $ShWin `
    -LogFile "~/.valiant_wsl_last.log" `
    -FailureContext "Failed to launch ArduPilot SITL" `
    -ExtraBashArgs @($args) `
    -Hints @(
        "Build SITL first: .\tools\setup_wsl.ps1",
        "Check: python tools\valiant.py diagnose"
    )
