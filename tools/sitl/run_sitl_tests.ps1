$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "..\lib\script_paths.ps1")
$ctx = Initialize-ValiantScript -ScriptRoot $PSScriptRoot
$Root = $ctx.RepoRoot
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
