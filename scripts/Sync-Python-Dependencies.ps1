[CmdletBinding()]
param(
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$backendRoot = Join-Path $repoRoot "backend"

if (-not $Python) {
    $venvPython = Join-Path $backendRoot ".venv\Scripts\python.exe"
    $Python = if (Test-Path $venvPython) {
        $venvPython
    } else {
        (Get-Command python -ErrorAction Stop).Source
    }
}

$version = & $Python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ($LASTEXITCODE -ne 0 -or $version.Trim() -ne "3.11") {
    throw "Python 3.11 is required to generate Relationship OS lock files."
}

& $Python -c "import piptools" 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "pip-tools is required. Install backend/requirements-build.txt first."
}

Push-Location $repoRoot
try {
    & $Python -m piptools compile `
        --generate-hashes `
        --allow-unsafe `
        --strip-extras `
        --resolver=backtracking `
        --output-file backend/requirements.txt `
        backend/requirements.in
    if ($LASTEXITCODE -ne 0) { throw "Runtime dependency locking failed." }

    & $Python -m piptools compile `
        --generate-hashes `
        --allow-unsafe `
        --strip-extras `
        --resolver=backtracking `
        --output-file backend/requirements-build.txt `
        backend/requirements-build.in
    if ($LASTEXITCODE -ne 0) { throw "Build dependency locking failed." }
} finally {
    Pop-Location
}

Write-Output "Python dependency locks are synchronized."
