[CmdletBinding()]
param(
    [switch]$Apply,
    [ValidateRange(0, 525600)]
    [int]$MinAgeMinutes = 60
)

$ErrorActionPreference = 'Stop'
$policyPath = Join-Path $PSScriptRoot 'evaluation-retention.json'
$outputPath = Join-Path $PSScriptRoot 'salida'
$runPattern = '^\d{8}T\d{6}Z_[0-9a-f]{12}$'
$reparse = [System.IO.FileAttributes]::ReparsePoint

function Test-NoReparsePoints([string]$Path) {
    $pending = New-Object 'System.Collections.Generic.Stack[string]'
    $pending.Push($Path)
    while ($pending.Count -gt 0) {
        $current = $pending.Pop()
        foreach ($entry in @(Get-ChildItem -LiteralPath $current -Force -ErrorAction Stop)) {
            if (($entry.Attributes -band $reparse) -ne 0) {
                return $false
            }
            if ($entry.PSIsContainer) {
                $pending.Push($entry.FullName)
            }
        }
    }
    return $true
}

function Test-IsAccessDenied([System.Management.Automation.ErrorRecord]$Record) {
    if ($Record.CategoryInfo.Category -eq [System.Management.Automation.ErrorCategory]::PermissionDenied) {
        return $true
    }
    $exception = $Record.Exception
    while ($null -ne $exception) {
        if ($exception -is [System.UnauthorizedAccessException]) {
            return $true
        }
        $exception = $exception.InnerException
    }
    return $false
}

if (-not (Test-Path -LiteralPath $policyPath -PathType Leaf)) {
    throw 'Missing evaluation-retention.json.'
}
$policy = Get-Content -LiteralPath $policyPath -Encoding UTF8 -Raw | ConvertFrom-Json
if ($policy.schema_version -ne 1 -or $null -eq $policy.keep_run_ids) {
    throw 'Invalid retention policy schema.'
}
$protected = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::OrdinalIgnoreCase)
foreach ($id in @($policy.keep_run_ids)) {
    if ($id -isnot [string] -or $id -cnotmatch $runPattern) {
        throw 'Retention policy contains an invalid run identifier.'
    }
    [void]$protected.Add($id)
}

if (-not (Test-Path -LiteralPath $outputPath -PathType Container)) {
    Write-Host 'No evaluation output directory exists; nothing to clean.'
    exit 0
}
$output = Get-Item -LiteralPath $outputPath -Force
if (($output.Attributes -band $reparse) -ne 0) {
    throw 'Refusing a reparse-point evaluation output directory.'
}
$cutoff = (Get-Date).ToUniversalTime().AddMinutes(-$MinAgeMinutes)
$deleted = 0
$candidates = 0
$skipped = 0
foreach ($directory in @(Get-ChildItem -LiteralPath $output.FullName -Directory -Force | Sort-Object Name)) {
    $reason = $null
    try {
        if (($directory.Attributes -band $reparse) -ne 0) {
            $reason = 'reparse point'
        } elseif ($directory.Name -cnotmatch $runPattern) {
            $reason = 'unrecognized name'
        } elseif ($protected.Contains($directory.Name)) {
            $reason = 'protected by JSON'
        } elseif ($directory.LastWriteTimeUtc -gt $cutoff) {
            $reason = 'too recent'
        } else {
            $manifestPath = Join-Path $directory.FullName 'manifest.json'
            if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
                $reason = 'missing manifest'
            } else {
                $manifestFile = Get-Item -LiteralPath $manifestPath -Force
                if (($manifestFile.Attributes -band $reparse) -ne 0) {
                    $reason = 'manifest is a reparse point'
                } else {
                    try {
                        $manifest = Get-Content -LiteralPath $manifestPath -Encoding UTF8 -Raw | ConvertFrom-Json
                        if ($manifest.run_id -cne $directory.Name -or
                            $manifest.artifacts_disposable -ne $true -or
                            @('COMPLETED', 'COMPLETED_WITH_ERRORS') -cnotcontains $manifest.status) {
                            $reason = 'manifest not eligible'
                        }
                    } catch {
                        $reason = 'unreadable manifest'
                    }
                }
            }
            if (-not $reason) {
                try {
                    if (-not (Test-NoReparsePoints $directory.FullName)) {
                        $reason = 'tree contains a reparse point'
                    }
                } catch {
                    $reason = 'tree cannot be safely inspected'
                }
            }
        }
    } catch {
        if (-not (Test-IsAccessDenied $_)) {
            throw
        }
        $reason = 'access denied'
    }
    if ($reason) {
        $skipped++
        Write-Host ('KEEP {0} ({1})' -f $directory.Name, $reason)
        continue
    }
    $candidates++
    if (-not $Apply) {
        Write-Host ('DRY RUN DELETE {0}' -f $directory.Name)
        continue
    }
    # This is deliberate deletion of persistent laboratory artifacts, not
    # portable-tempdirs-managed cleanup. Use only on a trusted local tree.
    try {
        Remove-Item -LiteralPath $directory.FullName -Recurse -Force -ErrorAction Stop
        if (Test-Path -LiteralPath $directory.FullName) {
            throw 'Directory is still present after removal.'
        }
        $deleted++
        Write-Host ('DELETED {0}' -f $directory.Name)
    } catch {
        Write-Warning ('Could not delete {0}: {1}' -f $directory.Name, $_.Exception.GetType().Name)
        throw 'Cleanup incomplete; stopped without attempting further deletions.'
    }
}
Write-Host ('Summary: candidates={0}, deleted={1}, retained={2}, apply={3}' -f $candidates, $deleted, $skipped, [bool]$Apply)
if (-not $Apply) {
    Write-Host 'No files were deleted. Use -Apply to execute this plan.'
}
