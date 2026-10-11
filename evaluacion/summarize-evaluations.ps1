[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$outputPath = Join-Path $PSScriptRoot 'salida'
$summaryPath = Join-Path $outputPath 'evaluation-summary.json'
$runPattern = '^\d{8}T\d{6}Z_[0-9a-f]{12}$'
$reparse = [System.IO.FileAttributes]::ReparsePoint

if (-not (Test-Path -LiteralPath $outputPath -PathType Container)) {
    [void](New-Item -ItemType Directory -Path $outputPath)
}
$root = Get-Item -LiteralPath $outputPath -Force
if (($root.Attributes -band $reparse) -ne 0) {
    throw 'Refusing a reparse-point output directory.'
}
if (Test-Path -LiteralPath $summaryPath) {
    $existingSummary = Get-Item -LiteralPath $summaryPath -Force
    if (($existingSummary.Attributes -band $reparse) -ne 0) {
        throw 'Refusing a reparse-point summary.'
    }
}

# PowerShell cmdlets may wrap UnauthorizedAccessException in an ErrorRecord.
# A protected historical run is incomplete evidence, not malformed JSON.
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

$runs = New-Object 'System.Collections.Generic.List[object]'
$skipped = New-Object 'System.Collections.Generic.List[object]'
$itemCount = 0
$successCount = 0
$errorCount = 0
$reviewCount = 0
$belowPreferredMinCount = 0

foreach ($directory in @(Get-ChildItem -LiteralPath $root.FullName -Directory -Force | Sort-Object Name)) {
    if ($directory.Name -cnotmatch $runPattern) {
        continue
    }
    if (($directory.Attributes -band $reparse) -ne 0) {
        $skipped.Add([pscustomobject]@{ run_id = $directory.Name; reason = 'reparse_point' })
        continue
    }
    try {
        $manifestPath = Join-Path $directory.FullName 'manifest.json'
        $resultsPath = Join-Path $directory.FullName 'results.json'
        if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf) -or
            -not (Test-Path -LiteralPath $resultsPath -PathType Leaf)) {
            $skipped.Add([pscustomobject]@{ run_id = $directory.Name; reason = 'missing_files' })
            continue
        }
        $manifestFile = Get-Item -LiteralPath $manifestPath -Force
        $resultsFile = Get-Item -LiteralPath $resultsPath -Force
        if ((($manifestFile.Attributes -band $reparse) -ne 0) -or
            (($resultsFile.Attributes -band $reparse) -ne 0)) {
            $skipped.Add([pscustomobject]@{ run_id = $directory.Name; reason = 'reparse_point' })
            continue
        }
        try {
            $manifest = Get-Content -LiteralPath $manifestPath -Encoding UTF8 -Raw | ConvertFrom-Json
            $rawResults = Get-Content -LiteralPath $resultsPath -Encoding UTF8 -Raw
            if (-not $rawResults.TrimStart().StartsWith('[')) {
                throw 'Expected a JSON array of results.'
            }
            # On Windows PowerShell 5.1, @( ... | ConvertFrom-Json )
            # can wrap a multi-row JSON array as one nested object[]. Assign
            # first, then enumerate the parsed value using foreach.
            $parsedResults = $rawResults | ConvertFrom-Json
        } catch {
            if (Test-IsAccessDenied $_) {
                throw
            }
            $skipped.Add([pscustomobject]@{ run_id = $directory.Name; reason = 'invalid_json' })
            continue
        }
        if ($manifest.run_id -cne $directory.Name -or
            $manifest.results_file -cne 'results.json' -or
            @('COMPLETED', 'COMPLETED_WITH_ERRORS') -cnotcontains $manifest.status) {
            $skipped.Add([pscustomobject]@{ run_id = $directory.Name; reason = 'not_final_or_invalid' })
            continue
        }
        $rows = New-Object 'System.Collections.Generic.List[object]'
        $invalidResults = $false
        foreach ($item in $parsedResults) {
            if ($null -eq $item -or $item.id -isnot [string] -or
                $item.status -isnot [string]) {
                $invalidResults = $true
                break
            }
            $label = $null
            $charCount = $null
            $provider = $null
            $needsSemanticReview = $false
            $belowPreferredMin = $false
            if ($null -ne $item.raw_output) {
                $label = $item.raw_output.label
                $charCount = $item.raw_output.char_count
                $provider = $item.raw_output.provider
                # Only export this safe, known warning category, never raw
                # provider output or arbitrary warning strings.
                foreach ($warning in @($item.raw_output.warnings)) {
                    if ($warning -is [string] -and
                        $warning.StartsWith('output_truncated:', [System.StringComparison]::Ordinal)) {
                        $needsSemanticReview = $true
                    }
                    if ($warning -is [string] -and $warning -ceq 'below_preferred_min_chars') {
                        $belowPreferredMin = $true
                    }
                }
            }
            $rows.Add([pscustomobject]@{
                case_id = $item.id
                repeat = $item.repeat
                status = $item.status
                label = $label
                char_count = $charCount
                provider = $provider
                needs_semantic_review = $needsSemanticReview
                below_preferred_min_chars = $belowPreferredMin
                diagnostic_category = $item.diagnostic_category
                provider_error_code = $item.provider_error_code
                objective_checks = $item.objective_checks
                input_sha256 = $item.input_sha256
            })
        }
        if ($invalidResults -or $rows.Count -eq 0) {
            $skipped.Add([pscustomobject]@{ run_id = $directory.Name; reason = 'malformed_results' })
            Write-Warning ('Cannot consolidate evaluation {0}: malformed results; report will be partial.' -f $directory.Name)
            continue
        }
        $itemCount += $rows.Count
        foreach ($row in $rows) {
            if ($row.status -ceq 'COMPLETED') {
                $successCount++
            } else {
                $errorCount++
            }
            if ($row.needs_semantic_review) {
                $reviewCount++
            }
            if ($row.below_preferred_min_chars) {
                $belowPreferredMinCount++
            }
        }
        $runs.Add([pscustomobject]@{
            run_id = $directory.Name
            set = $manifest.set
            batch = $manifest.batch
            status = $manifest.status
            provider_requested = $manifest.provider_requested
            started_utc = $manifest.started_utc
            completed_utc = $manifest.completed_utc
            bridge_calls_attempted = $manifest.bridge_calls_attempted
            bridge_results_received = $manifest.bridge_results_received
            inferences_confirmed = $manifest.inferences_confirmed
            results = @($rows.ToArray())
        })
    } catch {
        if (-not (Test-IsAccessDenied $_)) {
            throw
        }
        $skipped.Add([pscustomobject]@{ run_id = $directory.Name; reason = 'access_denied' })
        Write-Warning ('Cannot read evaluation {0}: access denied; report will be partial.' -f $directory.Name)
    }
}
$report = [ordered]@{
    schema_version = 1
    generated_utc = (Get-Date).ToUniversalTime().ToString('o')
    source = 'evaluacion/salida'
    complete = ($skipped.Count -eq 0)
    totals = [ordered]@{
        runs = $runs.Count
        results = $itemCount
        completed_results = $successCount
        other_results = $errorCount
        results_requiring_review = $reviewCount
        results_below_preferred_minimum = $belowPreferredMinCount
        skipped_directories = $skipped.Count
    }
    runs = @($runs.ToArray())
    skipped = @($skipped.ToArray())
}
$json = $report | ConvertTo-Json -Depth 15
$temp = Join-Path $root.FullName ('.evaluation-summary-' + [guid]::NewGuid().ToString('N') + '.tmp')
# .NET Framework on Windows PowerShell 5.1 requires a valid backup filename
# for File.Replace; passing $null fails with "The path is not of a legal form".
$backup = Join-Path $root.FullName ('.evaluation-summary-backup-' + [guid]::NewGuid().ToString('N') + '.bak')
$replaced = $false
try {
    [System.IO.File]::WriteAllText($temp, $json + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))
    if (Test-Path -LiteralPath $summaryPath) {
        [System.IO.File]::Replace($temp, $summaryPath, $backup)
        $replaced = $true
    } else {
        [System.IO.File]::Move($temp, $summaryPath)
    }
} finally {
    if (Test-Path -LiteralPath $temp) {
        Remove-Item -LiteralPath $temp -Force
    }
    # If replacement failed partway, preserve the backup for recovery.
    if ($replaced -and (Test-Path -LiteralPath $backup)) {
        Remove-Item -LiteralPath $backup -Force
    }
}
Write-Host ('Consolidated {0} runs and {1} results; skipped {2} directories; complete={3}.' -f $runs.Count, $itemCount, $skipped.Count, ($skipped.Count -eq 0))
Write-Output $summaryPath
