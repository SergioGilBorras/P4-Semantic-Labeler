[CmdletBinding()]
param(
    [ValidateSet('piloto', 'calibracion', 'regresion', 'reserva', 'acumulada', 'lote')]
    [string]$SetName = 'piloto',
    [string]$Batch,
    [string[]]$CaseIds = @(),
    [string]$PythonExecutable,
    [ValidateRange(1, 10)]
    [int]$Repetitions = 1,
    [ValidateRange(0, 1)]
    [int]$ReductionAttempts = 0,
    [ValidateRange(1, 1000)]
    [int]$MaxCases = 8,
    [ValidateRange(1, 10000)]
    [int]$MaxCalls = 8,
    [ValidateRange(1, 3600)]
    [int]$Timeout = 120,
    [switch]$Real,
    [switch]$ApproveReal
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = $PythonExecutable
if ([string]::IsNullOrWhiteSpace($python)) {
    $python = Join-Path $projectRoot '.venv\Scripts\python.exe'
}
$reporter = Join-Path $PSScriptRoot 'summarize-evaluations.ps1'
$runPattern = '^\d{8}T\d{6}Z_[0-9a-f]{12}$'
$casePattern = '^[A-Za-z][A-Za-z0-9_-]{1,70}$'

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw 'Project Python .venv was not found.'
}
if ($Real -and -not $ApproveReal) {
    throw 'Real inference requires both -Real and -ApproveReal.'
}
if ($ApproveReal -and -not $Real) {
    throw '-ApproveReal requires -Real.'
}
if ($SetName -eq 'lote' -and [string]::IsNullOrWhiteSpace($Batch)) {
    throw 'A named lote requires -Batch.'
}
if ($SetName -ne 'lote' -and -not [string]::IsNullOrWhiteSpace($Batch)) {
    throw '-Batch is only supported with -SetName lote.'
}
if ($SetName -eq 'lote' -and $Batch -cnotmatch $casePattern) {
    throw 'Invalid batch identifier.'
}
$seen = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::Ordinal)
foreach ($id in $CaseIds) {
    if ($null -eq $id -or $id -cnotmatch $casePattern -or -not $seen.Add($id)) {
        throw 'Case identifiers must be safe and unique.'
    }
}
if ($CaseIds.Count -gt 0 -and
    ($CaseIds.Count -gt $MaxCases -or ([long]$CaseIds.Count * $Repetitions * (1 + $ReductionAttempts)) -gt $MaxCalls)) {
    throw 'Requested case count or repetitions exceed the total run limits.'
}
if ($CaseIds.Count -eq 0) {
    $plan = @($null)
} else {
    $plan = @($CaseIds)
}

$runFailed = $false
$reportFailed = $false
$completed = 0
try {
    foreach ($caseId in $plan) {
        $callsForRun = $MaxCalls
        if ($null -ne $caseId) {
            $callsForRun = $Repetitions * (1 + $ReductionAttempts)
        }
        $arguments = @(
            '-m', 'evaluacion.herramientas.lab', 'run',
            '--set', $SetName,
            '--repetitions', [string]$Repetitions,
            '--max-cases', [string]$MaxCases,
            '--max-calls', [string]$callsForRun,
            '--reduction-attempts', [string]$ReductionAttempts,
            '--timeout', [string]$Timeout
        )
        if ($SetName -eq 'lote') {
            $arguments += @('--batch', $Batch)
        }
        if ($null -ne $caseId) {
            $arguments += @('--case', $caseId)
        }
        if ($Real) {
            $arguments += @('--real', '--approve-real')
        }
        Write-Host ('Starting evaluation: set={0} case={1} real={2}, call limit={3}, reduction retries={4}' -f $SetName, $caseId, [bool]$Real, $callsForRun, $ReductionAttempts)
        Push-Location -LiteralPath $projectRoot
        try {
            $lines = @(& $python @arguments 2>$null)
            $runnerExit = $LASTEXITCODE
        } finally {
            Pop-Location
        }
        if ($runnerExit -ne 0) {
            throw ('Evaluation runner returned exit code {0}.' -f $runnerExit)
        }
        $result = ($lines -join [Environment]::NewLine) | ConvertFrom-Json
        if ($null -eq $result -or $result.run_id -isnot [string] -or
            $result.run_id -cnotmatch $runPattern -or
            $result.directory -isnot [string]) {
            throw 'The runner did not return a valid run identity and directory.'
        }
        $runDir = [System.IO.Path]::GetFullPath($result.directory)
        $expectedParent = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'salida'))
        if (-not [System.StringComparer]::OrdinalIgnoreCase.Equals(
                [System.IO.Path]::GetDirectoryName($runDir), $expectedParent) -or
            [System.IO.Path]::GetFileName($runDir) -cne $result.run_id) {
            throw 'The runner returned a directory outside the evaluation output.'
        }
        Write-Host ('Run: {0} status={1} confirmed={2}' -f $result.run_id, $result.status, $result.inferences_confirmed)
        $completed++
        if ($result.status -cne 'COMPLETED' -or
            ($Real -and [int]$result.inferences_confirmed -lt 1)) {
            throw ('Evaluation did not complete successfully: {0}' -f $result.run_id)
        }
    }
} catch {
    $runFailed = $true
    Write-Warning ('Evaluation batch stopped: {0}' -f $_.Exception.Message)
} finally {
    try {
        $summaryPath = & $reporter
        Write-Host ('Shareable report: {0}' -f $summaryPath)
        Write-Output $summaryPath
    } catch {
        $reportFailed = $true
        Write-Warning ('Could not create consolidated report: {0}' -f $_.Exception.GetType().Name)
    }
}
Write-Host ('Executed {0} run(s); evaluation_success={1}; report_success={2}.' -f $completed, (-not $runFailed), (-not $reportFailed))
if ($runFailed -or $reportFailed) {
    exit 1
}
