$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Write-Host "Starting ArduPilot SITL in WSL..."
Write-Host "Requires ~/ardupilot in WSL — see docs\runbooks\sitl-wsl.md"
Write-Host "Companion connects: tcp:127.0.0.1:5760"
Write-Host ""
wsl bash "$Root/tools/sitl/launch_sitl.sh" @args
