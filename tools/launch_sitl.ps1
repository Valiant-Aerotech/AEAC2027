$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ShWin = Join-Path $Root "tools\sitl\launch_sitl.sh"
. (Join-Path $PSScriptRoot "wsl_distro.ps1")

Write-Host "Starting ArduPilot SITL in WSL..."
Write-Host "Requires ~/ardupilot in WSL - run .\tools\setup_wsl.ps1 if not built yet"
Write-Host "Companion connects: tcp:127.0.0.1:5760 (no MAVProxy required)"
Write-Host ""

if (-not (Test-Path $ShWin)) {
    Write-Error "Missing script: $ShWin"
}

if (-not (Test-ValiantWslReady)) {
    Write-Host "ERROR: WSL Ubuntu not ready. Run: .\tools\setup_wsl.ps1" -ForegroundColor Red
    exit 1
}

$distro = Get-ValiantWslDistro
Write-Host "Using WSL distro: $distro" -ForegroundColor DarkGray

$ShForward = $ShWin -replace '\\', '/'
$WslScript = (wsl -d $distro wslpath -a $ShForward).Trim()
$wslArgs = @("bash", $WslScript)
if ($args.Count -gt 0) {
    $wslArgs += $args
}
$code = Invoke-ValiantWsl -WslArgs $wslArgs
exit $code
