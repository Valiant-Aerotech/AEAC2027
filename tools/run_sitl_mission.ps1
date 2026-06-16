param(
    [string]$Profile = "sitl",
    [string]$Video = "",
    [string]$Scenario = "tests\fixtures\sitl_approach.json",
    [switch]$NoMonitor,
    [switch]$Headless
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$env:PYTHONPATH = "src"

$missionArgs = @(
    "missions\task2_vion_auto_extinguish.py",
    "--sitl",
    "--profile", $Profile,
    "--max-targets", "1"
)
if ($Video) {
    $missionArgs += @("--video", $Video)
}
elseif ($Scenario) {
    $missionArgs += @("--scenario", $Scenario)
}
if ($Headless) {
    $missionArgs += "--headless"
}

if (-not $NoMonitor) {
    Start-Process powershell -ArgumentList @(
        "-NoExit", "-Command",
        "cd '$Root'; `$env:PYTHONPATH='src'; python tools\mission_monitor.py"
    )
    Start-Sleep -Seconds 1
}

Write-Host "Starting SITL mission: $($missionArgs -join ' ')"
python @missionArgs
