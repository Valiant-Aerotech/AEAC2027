$scriptPath = Join-Path $PSScriptRoot '..\scripts\sitl.ps1'
$source = Get-Content -LiteralPath $scriptPath -Raw
$tokens = $null
$parseErrors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseInput(
    $source,
    [ref]$tokens,
    [ref]$parseErrors
)
$ast.FindAll({
    param($node)
    $node -is [System.Management.Automation.Language.FunctionDefinitionAst]
}, $true) | ForEach-Object {
    Invoke-Expression $_.Extent.Text
}

Describe 'SITL launcher preflight' {
    It 'stores and invalidates successful preflight results' {
        $originalCache = $PreflightCache
        $PreflightCache = Join-Path $TestDrive 'sitl-preflight.json'
        try {
            Set-PreflightCache -Ready $true
            Test-PreflightCache | Should Be $true

            Set-PreflightCache -Ready $false
            Test-PreflightCache | Should Be $false
        }
        finally {
            $PreflightCache = $originalCache
        }
    }

    It 'skips cached checks only for an ordinary launch' {
        $branchMatch = [regex]::Match(
            $source,
            '(?s)\$useCachedPreflight =.*?(?=\r?\n\$Choice = Select-SiteChoice)'
        )
        $branchMatch.Success | Should Be $true
        $branch = $branchMatch.Value `
            -replace 'exit 0', "throw 'AEAC_EXIT_0'" `
            -replace 'exit 1', "throw 'AEAC_EXIT_1'"

        function Invoke-BranchCase {
            param(
                [bool]$Check,
                [bool]$ForceRecheck,
                [bool]$Cached,
                [bool]$Ready
            )
            $calls = [ordered]@{
                CacheTests = 0
                CacheWrites = @()
                Preflights = 0
            }
            function Test-PreflightCache { $calls.CacheTests++; return $Cached }
            function Set-PreflightCache { param([bool]$Ready) $calls.CacheWrites += $Ready }
            function Invoke-SitlPreflight {
                $calls.Preflights++
                return [pscustomobject]@{ Ready = $Ready; Results = @() }
            }
            function Invoke-PreflightRepair { return $false }

            $CheckOnly = $Check
            $Recheck = $ForceRecheck
            $exitCode = $null
            try {
                Invoke-Expression $branch
            }
            catch {
                if ($_.Exception.Message -match '^AEAC_EXIT_(\d)$') {
                    $exitCode = [int]$Matches[1]
                }
                else {
                    throw
                }
            }
            return [pscustomobject]@{ Calls = $calls; ExitCode = $exitCode }
        }

        $cachedLaunch = Invoke-BranchCase $false $false $true $true
        $cachedLaunch.Calls.CacheTests | Should Be 1
        $cachedLaunch.Calls.Preflights | Should Be 0
        $cachedLaunch.Calls.CacheWrites.Count | Should Be 0

        $checkOnly = Invoke-BranchCase $true $false $true $true
        $checkOnly.Calls.CacheTests | Should Be 0
        $checkOnly.Calls.Preflights | Should Be 1
        $checkOnly.Calls.CacheWrites.Count | Should Be 2
        $checkOnly.ExitCode | Should Be 0

        $recheck = Invoke-BranchCase $false $true $true $true
        $recheck.Calls.CacheTests | Should Be 0
        $recheck.Calls.Preflights | Should Be 1
        $recheck.Calls.CacheWrites.Count | Should Be 2
    }

    It 'registers ForceCheck as an alias for Recheck' {
        $aliases = (Get-Command -Name $scriptPath).Parameters['Recheck'].Aliases
        ($aliases -contains 'ForceCheck') | Should Be $true
    }

    It 'completes repair progress after a terminating WSL error' {
        Mock Write-Progress {}
        Mock Read-Host { return 'y' }
        Mock Write-BashFile { return '/tmp/mock-repair.sh' }

        $results = @([pscustomobject]@{
            Status = 'fail'
            AptPackages = @('curl')
            Id = 'wsl.command'
            Repair = ''
        })
        $caughtError = $null
        try {
            Invoke-PreflightRepair -Results $results -RepairRunner { throw 'mock terminating WSL error' }
        }
        catch {
            $caughtError = $_
        }

        $caughtError.Exception.Message | Should Be 'mock terminating WSL error'
        Assert-MockCalled Write-Progress -Times 1 -ParameterFilter {
            $Id -eq 2 -and $Completed
        }
    }
}

Describe 'SITL site selector' {
    BeforeEach {
        $global:Sites = [ordered]@{
            '1' = @{ Name = 'Alpha site' }
            '2' = @{ Name = 'Bravo site' }
            '3' = @{ Name = 'Charlie site' }
        }
    }

    It 'keeps each option within the available console width' {
        Mock Write-Host {}

        Write-SiteMenuOption -Index 0 -SelectedIndex 0 -Top 0 -Pad 5 -Keys @('1', '2', '3')

        Assert-MockCalled Write-Host -Times 1 -ParameterFilter {
            $Object -eq '  1. ' -and $NoNewline
        }
    }

    It 'repaints only the previous and current options after movement' {
        Mock Write-Host {}
        $repaintedOptions = New-Object System.Collections.ArrayList
        function Write-SiteMenuOption {
            param($Index, $SelectedIndex, $Top, $Pad, $Keys)
            $repaintedOptions.Add([pscustomobject]@{
                Index = $Index
                SelectedIndex = $SelectedIndex
            }) | Out-Null
        }

        Show-SiteMenu -Index 1 -PreviousIndex 0 -Top 0 -Pad 20 -Keys @('1', '2', '3')

        $repaintedOptions.Count | Should Be 2
        $repaintedOptions[0].Index | Should Be 0
        $repaintedOptions[0].SelectedIndex | Should Be 1
        $repaintedOptions[1].Index | Should Be 1
        $repaintedOptions[1].SelectedIndex | Should Be 1
    }
}