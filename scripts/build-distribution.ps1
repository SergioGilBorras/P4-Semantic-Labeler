[CmdletBinding()]
param([string]$PythonExecutable)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$workDirs = @()
$buildExisted = Test-Path -LiteralPath (Join-Path $root 'build')

Push-Location -LiteralPath $root
try {
    $changes = @(git status --porcelain)
    if ($LASTEXITCODE -ne 0) { throw 'Git status failed. Run this inside the repository.' }
    if ($changes.Count -gt 0) { throw 'Tracked or untracked changes found. Commit or save them before packaging.' }

    if ($PythonExecutable) {
        $python = (Resolve-Path -LiteralPath $PythonExecutable).Path
    } elseif (Test-Path -LiteralPath '.\.venv\Scripts\python.exe') {
        $python = (Resolve-Path -LiteralPath '.\.venv\Scripts\python.exe').Path
    } else {
        $python = (Get-Command python -ErrorAction Stop).Source
    }
    & $python -c "import tomllib; from pathlib import Path; p=tomllib.loads(Path('pyproject.toml').read_text(encoding='utf-8')); assert p['project']['name']=='p4-semantic-labeler'; print(p['project']['version'])"
    if ($LASTEXITCODE -ne 0) { throw 'Unable to read Python project metadata.' }
    $version = (& $python -c "import tomllib; from pathlib import Path; print(tomllib.loads(Path('pyproject.toml').read_text(encoding='utf-8'))['project']['version'])").Trim()
    if ($LASTEXITCODE -ne 0 -or $version -notmatch '^\d+\.\d+\.\d+$') { throw 'Invalid declared package version.' }

    $dist = Join-Path $root 'dist'
    $wheel = Join-Path $dist ("p4_semantic_labeler-$version-py3-none-any.whl")
    $sdist = Join-Path $dist ("p4_semantic_labeler-$version.tar.gz")
    if (Test-Path -LiteralPath $dist) {
        if (@(Get-ChildItem -LiteralPath $dist -Force).Count -gt 0) {
            throw 'dist/ contains files. Review or archive them before creating a fresh distribution.'
        }
    }

    foreach ($folderName in @('.package-venv', '.package-sdist-venv')) {
        if (Test-Path -LiteralPath $folderName) {
            throw "Verification folder '$folderName' already exists; not overwriting it."
        }
    }

    & $python -m pip install build
    if ($LASTEXITCODE -ne 0) { throw 'Unable to install the PEP 517 build frontend.' }
    & $python -m build --outdir dist
    if ($LASTEXITCODE -ne 0) { throw 'Wheel/source build failed.' }
    if (-not (Test-Path -LiteralPath $wheel) -or -not (Test-Path -LiteralPath $sdist)) {
        throw 'Expected .whl and .tar.gz were not both created.'
    }
    if (@(Get-ChildItem -LiteralPath $dist -File).Count -ne 2) {
        throw 'Unexpected files were generated in dist/. Review the output before delivery.'
    }

    $inspect = "import sys,tarfile,zipfile; z=zipfile.ZipFile(sys.argv[1]); t=tarfile.open(sys.argv[2]); w=z.namelist(); s=t.getnames(); assert any(x.endswith('prompts/label_system.txt') for x in w); assert any(x.endswith('docs/distribution.md') for x in s); assert any(x.endswith('examples/README.md') for x in s); assert any(x.endswith('AUTHORS.md') for x in s); assert any(x.endswith('LICENSE') for x in s); print('Archive contents OK')"
    & $python -c $inspect $wheel $sdist
    if ($LASTEXITCODE -ne 0) { throw 'Distribution archive content check failed.' }

    $smoke = "from importlib import metadata,resources; from p4_semantic_labeler import Labeler,LabelRequest,Subject; from p4_semantic_labeler.config import Settings; import sys; assert metadata.version('p4-semantic-labeler') == sys.argv[1]; assert resources.files('p4_semantic_labeler.prompts').joinpath('label_system.txt').is_file(); assert metadata.version('portable-tempdirs')=='0.1.2'; x=Labeler(settings=Settings(provider='mock')).generate(LabelRequest(subject=Subject(name='process_pending_orders'),max_chars=45)); assert x.label=='process pending orders'; print('Installed package OK')"
    foreach ($pair in @(@('.package-venv', $wheel), @('.package-sdist-venv', $sdist))) {
        $folder = Join-Path $root $pair[0]
        $workDirs += $folder
        & $python -m venv $folder
        if ($LASTEXITCODE -ne 0) { throw "Failed creating test venv for $($pair[0])." }
        $verifier = Join-Path $folder 'Scripts\python.exe'
        & $verifier -m pip install $pair[1]
        if ($LASTEXITCODE -ne 0) { throw "Failed installing $($pair[1])." }
        & $verifier -m pip check
        if ($LASTEXITCODE -ne 0) { throw "pip check failed for $($pair[0])." }
        & $verifier -c $smoke $version
        if ($LASTEXITCODE -ne 0) { throw "Mock package smoke test failed for $($pair[0])." }
    }
    Write-Host "Verified files in dist/:"
    Get-ChildItem -LiteralPath $dist -File | Select-Object Name, Length | Format-Table
    Write-Host 'SHA-256 checksums:'
    Get-ChildItem -LiteralPath $dist -File | Get-FileHash -Algorithm SHA256 | Format-Table
    Write-Host 'Both archives built and installed successfully. No Codex inference was invoked.'
} finally {
    foreach ($folder in $workDirs) {
        if (Test-Path -LiteralPath $folder) {
            Remove-Item -LiteralPath $folder -Recurse -Force
        }
    }
    $buildPath = Join-Path $root 'build'
    if (-not $buildExisted -and (Test-Path -LiteralPath $buildPath)) {
        Remove-Item -LiteralPath $buildPath -Recurse -Force
    }
    Pop-Location
}
