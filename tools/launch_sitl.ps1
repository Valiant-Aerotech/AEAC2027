$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ShWin = Join-Path $Root "tools\sitl\launch_sitl.sh"

Write-Host "Starting ArduPilot SITL in WSL..."
Write-Host "Requires ~/ardupilot in WSL - see docs\runbooks\sitl-wsl.md"
Write-Host "Companion connects: tcp:127.0.0.1:5760 (no MAVProxy required)"
Write-Host ""

if (-not (Test-Path $ShWin)) {
    Write-Error "Missing script: $ShWin"
}

# wslpath needs forward slashes (A:/foo/bar), not Windows backslashes
$ShForward = $ShWin -replace '\\', '/'
$WslScript = (wsl wslpath -a $ShForward).Trim()
wsl bash $WslScript @args
