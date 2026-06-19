$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
. (Join-Path $PSScriptRoot "lib\diagnostics.ps1")
$env:PYTHONPATH = "src"

Write-Host "SITL integration tests (requires SITL running for some tests)" -ForegroundColor Yellow
$pytestArgs = @(
    "python", "-m", "pytest",
    "tests/test_sitl_search.py",
    "tests/test_sitl_motion.py",
    "tests/test_sitl_dashboard.py",
    "tests/test_synthetic_multi_camera.py",
    "tests/sitl",
    "-v"
) + $args
Invoke-ValiantPythonStep -Label "pytest SITL suite" -Arguments $pytestArgs -Hints @(
    "Start SITL first: .\tools\launch_sitl.ps1",
    "Or run offline unit tests only: pytest tests/test_sitl_motion.py -q"
)
