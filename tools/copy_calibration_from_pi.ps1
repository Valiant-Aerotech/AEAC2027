# Copy Pi calibration captures to GCS laptop (bringup Phase C6)
param(
    [Parameter(Mandatory = $true)]
    [string]$PiHost,

    [string]$PiPath = "~/AEAC2027",
    [string]$LocalDir = "logs\calibration"
)
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$dest = Join-Path $RepoRoot $LocalDir
New-Item -ItemType Directory -Force -Path $dest | Out-Null

Write-Host "Copying calibration from $PiHost..."
scp -r "${PiHost}:${PiPath}/logs/calibration/*" $dest

Write-Host "OK. Run: python tools\valiant.py calibrate validate --calibration-dir $LocalDir"
