param(
    [Parameter(Mandatory = $true)]
    [string]$Mission,
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

$missionArgs = @(
    "tools\sitl\run_sitl_mission_file.py",
    $Mission
)
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

Write-Host "SITL YAML mission: $Mission"
$py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }
$env:PYTHONPATH = "src"
& $py @missionArgs
exit $LASTEXITCODE
