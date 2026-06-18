$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$env:PYTHONPATH = "src"
python -m pytest `
    tests/test_sitl_search.py `
    tests/test_sitl_motion.py `
    tests/test_sitl_dashboard.py `
    tests/test_synthetic_multi_camera.py `
    tests/sitl `
    -v @args
