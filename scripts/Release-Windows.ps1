[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern("^\d+\.\d+\.\d+$")]
    [string]$Version,
    [string]$FlutterRoot = $env:FLUTTER_ROOT,
    [string]$Git = "",
    [string]$Python = "",
    [string]$InnoSetup = "",
    [switch]$SkipBackendBuild,
    [switch]$SkipFlutterTests,
    [switch]$SkipFlutterBuild,
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$frontendRoot = Join-Path $repoRoot "frontend"
$outputRoot = Join-Path $repoRoot "dist"
$packageName = "RelationshipOS-Windows-x64-$Version"
$packageRoot = Join-Path $outputRoot $packageName

$machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
[Environment]::SetEnvironmentVariable("PATH", $null, "Process")
[Environment]::SetEnvironmentVariable(
    "Path",
    "$machinePath;$userPath",
    "Process"
)

if (-not $FlutterRoot) {
    $flutterCommand = Get-Command flutter -ErrorAction SilentlyContinue
    $flutterCandidates = @(
        $(if ($flutterCommand) {
            Split-Path -Parent (Split-Path -Parent $flutterCommand.Source)
        }),
        (Join-Path $env:USERPROFILE "development\flutter"),
        (Join-Path $env:USERPROFILE "flutter")
    )
    $FlutterRoot = $flutterCandidates |
        Where-Object {
            $_ -and (Test-Path (Join-Path $_ "bin\cache\flutter_tools.snapshot"))
        } |
        Select-Object -First 1
}
$dart = Join-Path $FlutterRoot "bin\cache\dart-sdk\bin\dart.exe"
$flutterSnapshot = Join-Path $FlutterRoot "bin\cache\flutter_tools.snapshot"
if (-not (Test-Path $dart) -or -not (Test-Path $flutterSnapshot)) {
    throw "Flutter SDK was not found. Pass -FlutterRoot or set FLUTTER_ROOT."
}

$backendExe = Join-Path $repoRoot "build\backend\dist\relationship_os_backend.exe"
if (-not $SkipBackendBuild) {
    $backendExe = & (Join-Path $PSScriptRoot "Build-Backend.ps1") `
        -Python $Python `
        -OutputDirectory (Join-Path $repoRoot "build\backend")
    $backendExe = $backendExe | Select-Object -Last 1
}
if (-not (Test-Path $backendExe)) {
    throw "Backend release output was not found: $backendExe"
}

$env:FLUTTER_ALREADY_LOCKED = "true"
$env:FLUTTER_SUPPRESS_ANALYTICS = "true"
$env:CI = "true"
$flutterAppData = Join-Path $repoRoot "build\flutter-appdata"
New-Item -ItemType Directory -Force -Path $flutterAppData | Out-Null
$previousAppData = $env:APPDATA
$env:APPDATA = $flutterAppData
if (-not $SkipFlutterBuild) {
    if (-not $Git) {
        $gitCommand = Get-Command git -ErrorAction SilentlyContinue
        $gitCandidates = @(
            $(if ($gitCommand) { $gitCommand.Source }),
            (Join-Path $env:ProgramFiles "Git\cmd\git.exe"),
            (Join-Path ${env:ProgramFiles(x86)} "Git\cmd\git.exe"),
            (Join-Path $env:LOCALAPPDATA "Programs\Git\cmd\git.exe")
        )
        $Git = $gitCandidates |
            Where-Object { $_ -and (Test-Path $_) } |
            Select-Object -First 1
    }
    if (-not $Git) {
        throw "Git was not found. Pass -Git with the path to git.exe."
    }
    $currentPath = [Environment]::GetEnvironmentVariable("Path", "Process")
    [Environment]::SetEnvironmentVariable(
        "Path",
        "$(Split-Path -Parent $Git);$currentPath",
        "Process"
    )

    Push-Location $frontendRoot
    try {
        if (-not $SkipFlutterTests) {
            & $dart $flutterSnapshot analyze --no-pub
            if ($LASTEXITCODE -ne 0) {
                throw "Flutter analysis failed with exit code $LASTEXITCODE."
            }
            & $dart $flutterSnapshot test --no-pub
            if ($LASTEXITCODE -ne 0) {
                throw "Flutter tests failed with exit code $LASTEXITCODE."
            }
        }
        & $dart $flutterSnapshot build windows `
            --release `
            --no-pub `
            --build-name $Version
        if ($LASTEXITCODE -ne 0) {
            throw "Flutter Windows build failed with exit code $LASTEXITCODE."
        }
    } finally {
        Pop-Location
        $env:APPDATA = $previousAppData
    }
} else {
    $env:APPDATA = $previousAppData
}

$flutterRelease = Join-Path $frontendRoot "build\windows\x64\runner\Release"
if (-not (Test-Path (Join-Path $flutterRelease "relationship_os.exe"))) {
    throw "Flutter release output was not found: $flutterRelease"
}

if (Test-Path $packageRoot) {
    Remove-Item -Recurse -Force $packageRoot
}
New-Item -ItemType Directory -Force -Path $packageRoot | Out-Null
Copy-Item -Recurse -Force (Join-Path $flutterRelease "*") $packageRoot
New-Item -ItemType Directory -Force -Path (Join-Path $packageRoot "backend") |
    Out-Null
Copy-Item -Force $backendExe `
    (Join-Path $packageRoot "backend\relationship_os_backend.exe")
Copy-Item -Force (Join-Path $repoRoot "WINDOWS_README.txt") $packageRoot
Set-Content -Encoding ascii -Path (Join-Path $packageRoot "VERSION") -Value $Version

$zipPath = Join-Path $outputRoot "$packageName.zip"
if (Test-Path $zipPath) {
    Remove-Item -Force $zipPath
}
Compress-Archive -Path (Join-Path $packageRoot "*") `
    -DestinationPath $zipPath `
    -CompressionLevel Optimal

$artifacts = @($zipPath)
if (-not $SkipInstaller) {
    if (-not $InnoSetup) {
        $candidates = @(
            "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
            "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
            "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
        )
        $InnoSetup = $candidates | Where-Object { Test-Path $_ } |
            Select-Object -First 1
    }
    if (-not $InnoSetup -or -not (Test-Path $InnoSetup)) {
        throw "Inno Setup 6 was not found. Install it or use -SkipInstaller."
    }

    & $InnoSetup `
        "/DMyAppVersion=$Version" `
        "/DSourceDir=$packageRoot" `
        "/DOutputDir=$outputRoot" `
        (Join-Path $repoRoot "installer\RelationshipOS.iss")
    if ($LASTEXITCODE -ne 0) {
        throw "Inno Setup failed with exit code $LASTEXITCODE."
    }
    $artifacts += Join-Path $outputRoot "RelationshipOS-Setup-$Version.exe"
}

$checksumPath = Join-Path $outputRoot "$packageName-SHA256.txt"
$checksumLines = foreach ($artifact in $artifacts) {
    $hash = Get-FileHash -Algorithm SHA256 $artifact
    "$($hash.Hash.ToLowerInvariant())  $([IO.Path]::GetFileName($artifact))"
}
Set-Content -Encoding ascii -Path $checksumPath -Value $checksumLines

Write-Host "Release $Version generated:"
$artifacts + $checksumPath | ForEach-Object { Write-Host "  $_" }
