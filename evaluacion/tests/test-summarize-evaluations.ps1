# Offline regression checks for Windows PowerShell 5.1 and PowerShell 7.
# Run only against an isolated fixture under the CI runner's temporary directory.
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($env:RUNNER_TEMP)) {
    throw 'These regression fixtures require an isolated CI RUNNER_TEMP.'
}
$fixture = Join-Path $env:RUNNER_TEMP ('semantic-summary-test-' + [guid]::NewGuid().ToString('N'))
$scriptRoot = Join-Path $fixture 'evaluacion'
$outputRoot = Join-Path $scriptRoot 'salida'
[void](New-Item -ItemType Directory -Path $outputRoot -Force)
$summaryScript = Join-Path $scriptRoot 'summarize-evaluations.ps1'
Copy-Item -LiteralPath (Join-Path $PSScriptRoot '..\summarize-evaluations.ps1') -Destination $summaryScript
$encoding = [System.Text.UTF8Encoding]::new($false)

function Add-FixtureRun {
    param(
        [string]$Id,
        [object[]]$Results = @(),
        [string]$Status = 'COMPLETED',
        [string]$Provider = 'mock',
        [AllowNull()][string]$LiteralResults = $null,
        [switch]$MissingManifest
    )
    $directory = Join-Path $outputRoot $Id
    [void](New-Item -ItemType Directory -Path $directory)
    if (-not $MissingManifest) {
        $manifest = [ordered]@{
            run_id = $Id
            results_file = 'results.json'
            status = $Status
            set = 'piloto'
            batch = $null
            provider_requested = $Provider
            started_utc = '2026-10-11T10:00:00Z'
            completed_utc = '2026-10-11T10:01:00Z'
            bridge_calls_attempted = 0
            bridge_results_received = 0
            inferences_confirmed = $(if ($Provider -eq 'codex' -and $Status -eq 'COMPLETED') { 1 } else { 0 })
        }
        [System.IO.File]::WriteAllText(
            (Join-Path $directory 'manifest.json'),
            (ConvertTo-Json -InputObject $manifest -Depth 10), $encoding)
    }
    if (-not $PSBoundParameters.ContainsKey('LiteralResults')) {
        # Explicitly construct a JSON array: Windows PowerShell 5.1 does not
        # consistently preserve object[] when bound to ConvertTo-Json -InputObject.
        $serializedRows = @($Results | ForEach-Object {
            ConvertTo-Json -InputObject $_ -Depth 15 -Compress
        })
        $body = '[' + ($serializedRows -join ',') + ']'
    } else {
        $body = $LiteralResults
    }
    [System.IO.File]::WriteAllText((Join-Path $directory 'results.json'), $body, $encoding)
    return $directory
}

function New-CompletedResult {
    param([string]$CaseId, [string]$Provider = 'mock')
    $label = 'Label ' + $CaseId
    return [pscustomobject]@{
        id = $CaseId
        repeat = 1
        status = 'COMPLETED'
        raw_output = [ordered]@{ label = $label; char_count = $label.Length; provider = $Provider }
        objective_checks = [ordered]@{ not_empty = $true; within_limit = $true }
        input_sha256 = 'fixture'
    }
}

function Assert-Equal {
    param($Actual, $Expected, [string]$Description)
    if ($Actual -ne $Expected) {
        throw ('{0}: expected {1}, got {2}' -f $Description, $Expected, $Actual)
    }
}

$truncated = New-CompletedResult 'SL-0001'
$truncated.raw_output['warnings'] = @('output_truncated: meaning may be incomplete')
[void](Add-FixtureRun '20261011T100001Z_111111111111' -Results @($truncated))
$multi = @(1..8 | ForEach-Object { New-CompletedResult ('SL-{0:D4}' -f $_) })
$multi[0].raw_output['warnings'] = @('context_missing')
$multi[1].raw_output['warnings'] = @('below_preferred_min_chars')
[void](Add-FixtureRun '20261011T100002Z_222222222222' -Results $multi)
[void](Add-FixtureRun '20261011T100003Z_333333333333' -Provider 'codex' -Results @((New-CompletedResult 'SL-0002' 'codex')))
$providerError = [pscustomobject]@{
    id = 'SL-0003'
    repeat = 1
    status = 'ERROR'
    raw_output = $null
    diagnostic_category = 'UNKNOWN'
    provider_error_code = 'CODEX_EXIT_NONZERO'
    input_sha256 = 'fixture'
}
[void](Add-FixtureRun '20261011T100004Z_444444444444' -Status 'COMPLETED_WITH_ERRORS' -Provider 'codex' -Results @($providerError))
$protected = Add-FixtureRun '20261011T100005Z_555555555555' -Results @((New-CompletedResult 'SL-0004'))
[void](Add-FixtureRun '20261011T100006Z_666666666666' -LiteralResults '[{"id":42,"status":"COMPLETED"}]')
[void](Add-FixtureRun '20261011T100007Z_777777777777' -LiteralResults '[{"id":')
[void](Add-FixtureRun '20261011T100008Z_888888888888' -LiteralResults '{"id":"SL-0005","status":"COMPLETED"}')
[void](Add-FixtureRun '20261011T100009Z_999999999999' -MissingManifest -Results @((New-CompletedResult 'SL-0005')))

# Override only the manifest lookup inside the copied script. No ACL is changed.
$global:SemanticTestDeniedManifest = Join-Path $protected 'manifest.json'
function global:Test-Path {
    param([string]$LiteralPath, [string]$PathType)
    if ($LiteralPath -ceq $global:SemanticTestDeniedManifest) {
        throw [System.UnauthorizedAccessException]::new('simulated access denied')
    }
    if ($PSBoundParameters.ContainsKey('PathType')) {
        Microsoft.PowerShell.Management\Test-Path -LiteralPath $LiteralPath -PathType $PathType
    } else {
        Microsoft.PowerShell.Management\Test-Path -LiteralPath $LiteralPath
    }
}
try {
    $path = & $summaryScript
    $partial = Get-Content -LiteralPath $path -Encoding UTF8 -Raw | ConvertFrom-Json
    Write-Host ('Fixture skip reasons: ' + (ConvertTo-Json -InputObject @($partial.skipped) -Compress -Depth 5))
    Assert-Equal $partial.complete $false 'Protected/malformed report must be partial'
    Assert-Equal $partial.totals.runs 4 'Valid run count with protected fixture'
    Assert-Equal $partial.totals.results 11 'Single + 8-case + real + provider-error result count'
    Assert-Equal $partial.totals.completed_results 10 'Completed result count'
    Assert-Equal $partial.totals.other_results 1 'Provider error result count'
    Assert-Equal $partial.totals.results_requiring_review 1 'Historical truncated output flagged'
    Assert-Equal $partial.totals.results_below_preferred_minimum 1 'Advisory minimum does not change run status'
    $truncatedRun = @($partial.runs | Where-Object { $_.run_id -eq '20261011T100001Z_111111111111' })
    Assert-Equal $truncatedRun[0].results[0].status 'COMPLETED' 'Historical status is not rewritten'
    Assert-Equal $truncatedRun[0].results[0].needs_semantic_review $true 'Truncation requires review'
    Assert-Equal $partial.totals.skipped_directories 5 'Skipped run count'
    foreach ($reason in @('access_denied', 'malformed_results', 'missing_files')) {
        Assert-Equal (@($partial.skipped | Where-Object { $_.reason -eq $reason }).Count) 1 "Skipped reason $reason"
    }
    Assert-Equal (@($partial.skipped | Where-Object { $_.reason -eq 'invalid_json' }).Count) 2 'Invalid JSON/non-array count'
    $batchRun = @($partial.runs | Where-Object { $_.run_id -eq '20261011T100002Z_222222222222' })
    Assert-Equal $batchRun.Count 1 'Multi-case run present'
    Assert-Equal (@($batchRun[0].results).Count) 8 'Eight results are independent rows'
    Assert-Equal $batchRun[0].results[0].needs_semantic_review $false 'Unrelated warnings are ignored'
    Assert-Equal $batchRun[0].results[1].below_preferred_min_chars $true 'Preferred minimum warning is exposed'
    Assert-Equal $batchRun[0].results[1].needs_semantic_review $false 'Advisory minimum is not review-required'
    Assert-Equal $batchRun[0].results[1].status 'COMPLETED' 'Advisory minimum does not block result'
    $errorRun = @($partial.runs | Where-Object { $_.run_id -eq '20261011T100004Z_444444444444' })
    Assert-Equal $errorRun[0].results[0].status 'ERROR' 'Provider error survives summarization'
} finally {
    Remove-Item -LiteralPath Function:\Test-Path -ErrorAction SilentlyContinue
    Remove-Variable SemanticTestDeniedManifest -Scope Global -ErrorAction SilentlyContinue
}

# Replacing an existing summary must work repeatedly and restore the protected run.
foreach ($attempt in 1..2) {
    $path = & $summaryScript
    $report = Get-Content -LiteralPath $path -Encoding UTF8 -Raw | ConvertFrom-Json
    Assert-Equal $report.totals.runs 5 ('Restored runs, attempt ' + $attempt)
    Assert-Equal $report.totals.results 12 ('Restored results, attempt ' + $attempt)
    Assert-Equal $report.totals.results_requiring_review 1 'Repeat retains review flag'
    Assert-Equal $report.totals.results_below_preferred_minimum 1 'Repeat retains advisory count'
    Assert-Equal $report.totals.skipped_directories 4 ('Remaining damaged fixtures, attempt ' + $attempt)
    Assert-Equal $report.complete $false 'Report remains partial for invalid historical fixtures'
}
Assert-Equal (@(Get-ChildItem -LiteralPath $outputRoot -File -Filter '.evaluation-summary-backup-*.bak').Count) 0 'No stale summary backups'
Assert-Equal (@(Get-ChildItem -LiteralPath $outputRoot -File -Filter '.evaluation-summary-*.tmp').Count) 0 'No stale summary temporary files'
Write-Host ('Offline summary regression checks passed under PowerShell {0}.' -f $PSVersionTable.PSVersion)
