param(
    [switch]$NoMonitor,
    [switch]$SkipPreflight,
    [int]$Laps = 0
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$missionArgs = @("tools\sitl\sitl_orbit_flight.py")
if ($SkipPreflight) {
    $missionArgs += "--skip-preflight"
}
if ($Laps -gt 0) {
    $missionArgs += @("--laps", $Laps)
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
    if (-not $portBusy) {
        Start-Process powershell -ArgumentList @(
            "-NoExit", "-Command",
            "cd '$Root'; `$env:PYTHONPATH='src'; python tools\valiant.py gcs monitor --port $monitorPort"
        )
        Start-Sleep -Seconds 1
    }
}

Write-Host "SITL orbit flight (circle + LOITER)"
$py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }
$env:PYTHONPATH = "src"
& $py @missionArgs
exit $LASTEXITCODE
