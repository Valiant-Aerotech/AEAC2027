param(
    [string]$Profile = "sitl",
    [string]$Video = "",
    [string]$Scenario = "",
    [int]$MaxTargets = 1,
    [switch]$Physics,
    [switch]$HardAngles,
    [switch]$NoMonitor,
    [switch]$Headless,
    [switch]$SkipPreflight,
    [switch]$SkipArm
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
. (Join-Path $PSScriptRoot "lib\diagnostics.ps1")

if ($SkipArm) {
    $SkipPreflight = $true
}

if ($Physics) {
    $Profile = "sitl_physics"
}
elseif ($HardAngles) {
    $Profile = "sitl"
    $Scenario = "tests\fixtures\sitl_approach_hard.json"
}

$maxTargets = "$MaxTargets"
$missionArgs = @(
    "missions\task2_vion_auto_extinguish.py",
    "--sitl",
    "--profile", $Profile,
    "--max-targets", $maxTargets
)
if ($Video) {
    $missionArgs += @("--video", $Video)
}
elseif ($Scenario -and $Profile -ne "sitl_physics") {
    $missionArgs += @("--scenario", $Scenario)
}
if ($Headless) {
    $missionArgs += "--headless"
}
if ($SkipPreflight) {
    $missionArgs += "--skip-sitl-preflight"
}

if (-not $NoMonitor) {
    $monitorPort = 14560
    $portBusy = $false
    try {
        $probe = New-Object System.Net.Sockets.UdpClient
        $probe.Client.SetSocketOption(
            [System.Net.Sockets.SocketOptionLevel]::Socket,
            [System.Net.Sockets.SocketOptionName]::ReuseAddress, $true)
        $probe.Client.Bind(([System.Net.IPEndPoint]::new([System.Net.IPAddress]::Any, $monitorPort)))
        $probe.Close()
    }
    catch {
        $portBusy = $true
    }
    if ($portBusy) {
        Write-ValiantWarn "Telemetry monitor already on UDP $monitorPort - skipping new window"
    }
    else {
        Start-Process powershell -ArgumentList @(
            "-NoExit", "-Command",
            "cd '$Root'; `$env:PYTHONPATH='src'; python tools\valiant.py gcs monitor --port $monitorPort"
        )
        Start-Sleep -Seconds 1
    }
}

Write-Host "SITL mission profile=$Profile max-targets=$MaxTargets"
Invoke-ValiantMissionPython -MissionArgs $missionArgs -Label "SITL mission"
