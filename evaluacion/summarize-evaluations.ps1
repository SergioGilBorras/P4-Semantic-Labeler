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

$runs = New-Object 'System.Collections.Generic.List[object]'
$skipped = New-Object 'System.Collections.Generic.List[object]'
$itemCount = 0
$successCount = 0
$errorCount = 0

foreach ($directory in @(Get-ChildItem -LiteralPath $root.FullName -Directory -Force | Sort-Object Name)) {
    if ($directory.Name -cnotmatch $runPattern) {
        continue
    }
    if (($directory.Attributes -band $reparse) -ne 0) {
        $skipped.Add([pscustomobject]@{ run_id = $directory.Name; reason = 'reparse_point' })
        continue
    }
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
        $items = @(Get-Content -LiteralPath $resultsPath -Encoding UTF8 -Raw | ConvertFrom-Json)
    } catch {
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
    foreach ($item in $items) {
        if ($null -eq $item -or $item.id -isnot [string] -or
            $item.status -isnot [string]) {
            throw ('Malformed result in evaluation {0}.' -f $directory.Name)
        }
        $label = $null
        $charCount = $null
        $provider = $null
        if ($null -ne $item.raw_output) {
            $label = $item.raw_output.label
            $charCount = $item.raw_output.char_count
            $provider = $item.raw_output.provider
        }
        $rows.Add([pscustomobject]@{
            case_id = $item.id
            repeat = $item.repeat
            status = $item.status
            label = $label
            char_count = $charCount
            provider = $provider
            diagnostic_category = $item.diagnostic_category
            provider_error_code = $item.provider_error_code
            objective_checks = $item.objective_checks
            input_sha256 = $item.input_sha256
        })
        $itemCount++
        if ($item.status -ceq 'COMPLETED') {
            $successCount++
        } else {
            $errorCount++
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
}
$report = [ordered]@{
    schema_version = 1
    generated_utc = (Get-Date).ToUniversalTime().ToString('o')
    source = 'evaluacion/salida'
    totals = [ordered]@{
        runs = $runs.Count
        results = $itemCount
        completed_results = $successCount
        other_results = $errorCount
        skipped_directories = $skipped.Count
    }
    runs = @($runs.ToArray())
    skipped = @($skipped.ToArray())
}
$json = $report | ConvertTo-Json -Depth 15
$temp = Join-Path $root.FullName ('.evaluation-summary-' + [guid]::NewGuid().ToString('N') + '.tmp')
try {
    [System.IO.File]::WriteAllText($temp, $json + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))
    if (Test-Path -LiteralPath $summaryPath) {
        [System.IO.File]::Replace($temp, $summaryPath, $null)
    } else {
        [System.IO.File]::Move($temp, $summaryPath)
    }
} finally {
    if (Test-Path -LiteralPath $temp) {
        Remove-Item -LiteralPath $temp -Force
    }
}
Write-Host ('Consolidated {0} runs and {1} results; skipped {2} directories.' -f $runs.Count, $itemCount, $skipped.Count)
Write-Output $summaryPath
