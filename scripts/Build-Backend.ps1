[CmdletBinding()]
param(
    [string]$Python = "",
    [string]$OutputDirectory = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$backendRoot = Join-Path $repoRoot "backend"
$specPath = Join-Path $PSScriptRoot "relationship_os_backend.spec"

if (-not $Python) {
    $venvPython = Join-Path $backendRoot ".venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        $Python = $venvPython
    } else {
        $Python = (Get-Command python -ErrorAction Stop).Source
    }
}
if (-not $OutputDirectory) {
    $OutputDirectory = Join-Path $repoRoot "build\backend"
}

$previousErrorPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& $Python -c "import PyInstaller" 2>$null
$pyInstallerCheckExitCode = $LASTEXITCODE
$ErrorActionPreference = $previousErrorPreference
if ($pyInstallerCheckExitCode -ne 0) {
    throw "PyInstaller is not installed. Run: `"$Python`" -m pip install pyinstaller"
}

$distPath = Join-Path $OutputDirectory "dist"
$workPath = Join-Path $OutputDirectory "work"
$existingExe = Join-Path $distPath "relationship_os_backend.exe"
if (Test-Path $existingExe) {
    try {
        Remove-Item -Force $existingExe
    } catch {
        throw "The previous backend EXE is in use. Close Relationship OS and retry: $existingExe"
    }
}
New-Item -ItemType Directory -Force -Path $distPath, $workPath | Out-Null

Push-Location $repoRoot
try {
    & $Python -m PyInstaller `
        --noconfirm `
        --clean `
        --distpath $distPath `
        --workpath $workPath `
        $specPath
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE."
    }
} finally {
    Pop-Location
}

$result = Join-Path $distPath "relationship_os_backend.exe"
if (-not (Test-Path $result)) {
    throw "Backend build output was not found: $result"
}
Write-Output $result
