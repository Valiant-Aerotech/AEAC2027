# Shared repo/tools path resolution for scripts in tools/ subfolders.
# Dot-source from tools/lib/diagnostics.ps1 (already loaded) or call directly.

function Get-ValiantToolsDirFromScript {
    param([string]$ScriptRoot = $PSScriptRoot)
    if (Test-Path -LiteralPath (Join-Path $ScriptRoot "valiant.py")) {
        return (Resolve-Path -LiteralPath $ScriptRoot).Path
    }
    return (Resolve-Path -LiteralPath (Join-Path $ScriptRoot "..")).Path
}

function Get-ValiantRepoRootFromScript {
    param([string]$ScriptRoot = $PSScriptRoot)
    $tools = Get-ValiantToolsDirFromScript -ScriptRoot $ScriptRoot
    return (Resolve-Path -LiteralPath (Join-Path $tools "..")).Path
}

function Initialize-ValiantScript {
    param([string]$ScriptRoot = $PSScriptRoot)
    $tools = Get-ValiantToolsDirFromScript -ScriptRoot $ScriptRoot
    $repo = (Resolve-Path -LiteralPath (Join-Path $tools "..")).Path
    Set-Location $repo
    . (Join-Path $tools "lib\diagnostics.ps1")
    return @{ RepoRoot = $repo; ToolsDir = $tools }
}
