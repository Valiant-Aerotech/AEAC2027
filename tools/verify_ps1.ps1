# Verify all PowerShell scripts parse and use ASCII-only text (Windows PowerShell 5.1 safe).
# Usage: .\tools\verify_ps1.ps1
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$files = Get-ChildItem -Path $RepoRoot -Filter "*.ps1" -Recurse |
    Where-Object { $_.FullName -notmatch '\\\.venv\\' }

$failed = @()
foreach ($f in $files) {
    $rel = $f.FullName.Substring($RepoRoot.Length + 1)
    $text = [System.IO.File]::ReadAllText($f.FullName)
    foreach ($ch in $text.ToCharArray()) {
        if ([int][char]$ch -gt 127) {
            $failed += "$rel : non-ASCII character U+$('{0:X4}' -f [int][char]$ch)"
            break
        }
    }
    $tokens = $null
    $errs = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile($f.FullName, [ref]$tokens, [ref]$errs)
    if ($errs -and $errs.Count -gt 0) {
        foreach ($e in $errs) {
            $failed += "$rel : parse error line $($e.Extent.StartLineNumber): $($e.Message)"
        }
    }
}

if ($failed.Count -eq 0) {
    Write-Host "OK: $($files.Count) PowerShell scripts parse cleanly (ASCII-only)" -ForegroundColor Green
    exit 0
}

Write-Host "FAILED: PowerShell script check" -ForegroundColor Red
$failed | ForEach-Object { Write-Host "  $_" -ForegroundColor Yellow }
exit 1
