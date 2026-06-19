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

if ($failed.Count -gt 0) {
    Write-Host "FAILED: PowerShell script check" -ForegroundColor Red
    $failed | ForEach-Object { Write-Host "  $_" -ForegroundColor Yellow }
    exit 1
}

. (Join-Path $RepoRoot "tools\wsl_distro.ps1")
$pathFailed = @()

$repoFromTools = Get-ValiantRepoRoot -FromScriptRoot (Join-Path $RepoRoot "tools")
if ($repoFromTools -ne $RepoRoot) {
    $pathFailed += "Get-ValiantRepoRoot mismatch: $repoFromTools vs $RepoRoot"
}

$sitlSh = Get-ValiantRepoPath -RelativePath "sitl\wsl_run.sh" -FromScriptRoot (Join-Path $RepoRoot "tools")
if (-not (Test-Path -LiteralPath $sitlSh)) {
    $pathFailed += "Get-ValiantRepoPath missing: $sitlSh"
}

$wslPath = ConvertTo-ValiantWslPath -WinPath $sitlSh
if ($wslPath -notmatch '^/mnt/[a-z]/') {
    $pathFailed += "ConvertTo-ValiantWslPath bad mount: $wslPath"
}
if ($wslPath -notmatch '/tools/sitl/wsl_run\.sh$') {
    $pathFailed += "ConvertTo-ValiantWslPath bad suffix: $wslPath"
}

$grepHits = Select-String -Path (Join-Path $RepoRoot "tools\*.ps1"), (Join-Path $RepoRoot "tools\lib\*.ps1") -Pattern '\bwslpath\b' -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -notlike '*\verify_ps1.ps1' }
if ($grepHits) {
    $pathFailed += "Raw wslpath still used in: $(($grepHits | Select-Object -ExpandProperty Path -Unique) -join ', ')"
}

if ($pathFailed.Count -gt 0) {
    Write-Host "FAILED: WSL path helper check" -ForegroundColor Red
    $pathFailed | ForEach-Object { Write-Host "  $_" -ForegroundColor Yellow }
    exit 1
}

Write-Host "OK: $($files.Count) PowerShell scripts parse cleanly (ASCII-only)" -ForegroundColor Green
Write-Host "OK: WSL path helpers (repo root + /mnt/ conversion)" -ForegroundColor Green
exit 0
