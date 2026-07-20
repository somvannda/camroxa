param(
    [Parameter(Mandatory = $false)]
    [ValidateSet("sandbox", "production")]
    [string]$Environment = "sandbox",

    # Force pip even when deps already import cleanly.
    [Parameter(Mandatory = $false)]
    [switch]$ForceInstall,

    # Kept for compatibility; same as default when deps are already present.
    [Parameter(Mandatory = $false)]
    [switch]$SkipInstall,

    [Parameter(Mandatory = $false)]
    [switch]$SkipInstallerAssets,

    # Wipe build/ + dist\Camxora before packaging (slow; use after packaging bugs).
    [Parameter(Mandatory = $false)]
    [switch]$Clean,

    [Parameter(Mandatory = $false)]
    [switch]$BuildInno
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Write-Phase([string]$Name) {
    $script:LastPhase = $Name
    $script:PhaseStarted = Get-Date
    Write-Host ""
    Write-Host ("=== {0} ===" -f $Name)
}

function Write-PhaseDone {
    if (-not $script:PhaseStarted) { return }
    $elapsed = (Get-Date) - $script:PhaseStarted
    Write-Host ("--- {0} done in {1:N1}s ---" -f $script:LastPhase, $elapsed.TotalSeconds)
}

$buildStarted = Get-Date

$envFile = if ($Environment -eq "production") { ".env.production" } else { ".env.sandbox" }
$exampleFile = "$envFile.example"

if (-not (Test-Path $envFile)) {
    if (-not (Test-Path $exampleFile)) {
        throw "Missing $envFile and $exampleFile"
    }
    Copy-Item $exampleFile $envFile
    Write-Host "Created $envFile from $exampleFile"
}

Get-Content $envFile | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) { return }
    $parts = $line.Split("=", 2)
    $key = $parts[0].Trim()
    $value = $parts[1].Trim().Trim('"').Trim("'")
    if ($key) {
        Set-Item -Path "Env:$key" -Value $value
    }
}

$env:CAMXORA_ENV_FILE = $envFile

function Test-DesktopBuildDeps {
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    python -W ignore -c @"
import importlib
required = [
    'PyInstaller', 'PySide6', 'app', 'moderngl', 'pygame', 'glfw',
    'OpenGL', 'librosa', 'soundfile', 'cv2', 'numpy', 'PIL',
]
missing = []
for name in required:
    try:
        importlib.import_module(name)
    except Exception as exc:
        missing.append(f'{name}: {exc}')
if missing:
    raise SystemExit(1)
"@
    $code = $LASTEXITCODE
    $ErrorActionPreference = $prevEap
    return ($code -eq 0)
}

$shouldInstall = $ForceInstall -or (-not $SkipInstall -and -not (Test-DesktopBuildDeps))
if ($SkipInstall -and $ForceInstall) {
    throw "Use either -SkipInstall or -ForceInstall, not both."
}

if ($shouldInstall) {
    Write-Phase "pip install"
    if (-not $ForceInstall) {
        Write-Host "Dependencies missing or incomplete â€” running pip install (use -ForceInstall to always run)."
    }
    # PowerShell Stop treats pip stderr WARNINGs as terminating NativeCommandError.
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    python -m pip install -e ".[dev]" pyinstaller
    $pipCode = $LASTEXITCODE
    $ErrorActionPreference = $prevEap
    if ($pipCode -ne 0) {
        throw "pip install failed with exit code $pipCode"
    }
    Write-PhaseDone
} else {
    Write-Host "Skipping pip install (deps already importable). Use -ForceInstall to refresh."
}

$vendorFfmpeg = Join-Path $Root "vendor\ffmpeg\ffmpeg.exe"
$vendorVc = Join-Path $Root "vendor\vcredist\vc_redist.x64.exe"
$assetsReady = (Test-Path $vendorFfmpeg) -and (Test-Path $vendorVc)

if (-not $SkipInstallerAssets) {
    if ($assetsReady) {
        Write-Host "Skipping installer asset download (vendor FFmpeg + VC++ already present)."
    } else {
        Write-Phase "installer assets"
        Write-Host "Preparing bundled FFmpeg + VC++ redistributable..."
        & (Join-Path $PSScriptRoot "prepare-installer-assets.ps1")
        Write-PhaseDone
    }
}

Write-Phase "GPU import check"
$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
python -W ignore -c @"
mods = ['moderngl', 'pygame', 'glfw', 'OpenGL', 'librosa', 'soundfile', 'cv2', 'numpy', 'PIL']
missing = []
for name in mods:
    try:
        __import__(name)
    except Exception as exc:
        missing.append(f'{name}: {exc}')
if missing:
    raise SystemExit('GPU packages missing before build:\n- ' + '\n- '.join(missing))
print('GPU preview packages OK')
"@
$gpuCheckCode = $LASTEXITCODE
$ErrorActionPreference = $prevEap
if ($gpuCheckCode -ne 0) {
    throw "GPU dependency check failed - fix pip install before packaging"
}
Write-PhaseDone

if ($Clean) {
    Write-Phase "clean build artifacts"
    if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
    if (Test-Path "dist\Camxora") { Remove-Item -Recurse -Force "dist\Camxora" }
    Write-Host "Removed build/ and dist\Camxora (full clean)."
    Write-PhaseDone
} else {
    # Keep build/ so PyInstaller can reuse Analysis TOC. Only refresh the onedir output.
    if (Test-Path "dist\Camxora") {
        Write-Host "Removing previous dist\Camxora (keeping build/ cache). Pass -Clean for a full wipe."
        Remove-Item -Recurse -Force "dist\Camxora"
    }
}

$version = (Select-String -Path (Join-Path $Root "pyproject.toml") -Pattern '^version\s*=\s*"([^"]+)"').Matches[0].Groups[1].Value
$versionFile = Join-Path $Root "resources\app-version.txt"
# utf8NoBOM: Windows PowerShell's "utf8" encoding writes a BOM that breaks semver parsing.
$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($versionFile, $version, $utf8NoBom)
Write-Host "Stamped app version $version into resources/app-version.txt"

Write-Phase "PyInstaller"
Write-Host "Building Camxora ($Environment)..."
$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
pyinstaller Camxora.spec --noconfirm
$pyInstallerCode = $LASTEXITCODE
$ErrorActionPreference = $prevEap
if ($pyInstallerCode -ne 0) {
    throw "PyInstaller failed with exit code $pyInstallerCode"
}
Write-PhaseDone

$outDir = Join-Path $Root "dist\Camxora"
$exe = Join-Path $outDir "Camxora.exe"
if (-not (Test-Path $exe)) {
    throw "Build failed: $exe not found"
}

Copy-Item $envFile (Join-Path $outDir $envFile) -Force

# Always publish UI chrome assets into the onedir bundle (logo + window controls).
$resourcesSrc = Join-Path $Root "resources"
$resourcesDest = Join-Path $outDir "_internal\resources"
if (-not (Test-Path $resourcesSrc)) {
    throw "Missing UI resources directory: $resourcesSrc"
}
New-Item -ItemType Directory -Force -Path $resourcesDest | Out-Null
Copy-Item (Join-Path $resourcesSrc "*") $resourcesDest -Force -Recurse
foreach ($required in @(
    "app-icon.ico",
    "app-logo.svg",
    "app-version.txt",
    "window-close.svg",
    "window-minimize.svg",
    "window-maximize.svg"
)) {
    if (-not (Test-Path (Join-Path $resourcesDest $required))) {
        throw "Missing required UI resource after package copy: $required"
    }
}
Write-Host "Bundled UI resources into $resourcesDest"

$internalData = Join-Path $outDir "_internal\data"
if (-not (Test-Path $internalData)) {
    New-Item -ItemType Directory -Path $internalData | Out-Null
}
# Factory sample catalog is optional and not auto-loaded by the app.
$factoryTemplates = Join-Path (Split-Path $Root -Parent) "python_app\video_templates_local.json"
if (Test-Path $factoryTemplates) {
    Copy-Item $factoryTemplates (Join-Path $internalData "video_templates_local.json") -Force
}

# Place FFmpeg next to Camxora.exe so resolve_ffmpeg_path finds it after install.
$vendorFfmpegDir = Join-Path $Root "vendor\ffmpeg"
$distFfmpeg = Join-Path $outDir "ffmpeg"
if (Test-Path (Join-Path $vendorFfmpegDir "ffmpeg.exe")) {
    New-Item -ItemType Directory -Force -Path $distFfmpeg | Out-Null
    Copy-Item (Join-Path $vendorFfmpegDir "ffmpeg.exe") (Join-Path $distFfmpeg "ffmpeg.exe") -Force
    if (Test-Path (Join-Path $vendorFfmpegDir "ffprobe.exe")) {
        Copy-Item (Join-Path $vendorFfmpegDir "ffprobe.exe") (Join-Path $distFfmpeg "ffprobe.exe") -Force
    }
    Write-Host "Bundled FFmpeg into $distFfmpeg"
}

Write-Phase "verify package"
python (Join-Path $PSScriptRoot "verify-desktop-dist.py") $outDir
if ($LASTEXITCODE -ne 0) {
    throw "Package verification failed"
}
Write-PhaseDone

if ($BuildInno) {
    Write-Phase "Inno Setup"
    $iscc = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
    if (-not $iscc) {
        $candidates = @(
            "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
            "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
        )
        foreach ($candidate in $candidates) {
            if (Test-Path $candidate) {
                $iscc = Get-Item $candidate
                break
            }
        }
    }
    if (-not $iscc) {
        throw "Inno Setup ISCC.exe not found. Install Inno Setup 6 or omit -BuildInno."
    }
    $version = (Select-String -Path (Join-Path $Root "pyproject.toml") -Pattern '^version\s*=\s*"([^"]+)"').Matches[0].Groups[1].Value
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & $iscc.FullName (Join-Path $Root "installer\Camxora.iss") "/DCamxoraVersion=$version"
    $isccCode = $LASTEXITCODE
    $ErrorActionPreference = $prevEap
    if ($isccCode -ne 0) {
        throw "Inno Setup build failed"
    }
    Write-Host "Installer written to dist\installer\"
    Write-PhaseDone
}

$total = (Get-Date) - $buildStarted
Write-Host ""
Write-Host "Built $Environment desktop bundle in $([int]$total.TotalSeconds)s:"
Write-Host "  $outDir"
Write-Host "  API: $env:CAMXORA_API_BASE_URL"
Write-Host "  Portal: $env:CAMXORA_PORTAL_BASE_URL"
$ffmpegOut = Join-Path $outDir "ffmpeg\ffmpeg.exe"
Write-Host "  FFmpeg: $ffmpegOut"
Write-Host "  Ship CamxoraSetup-*.exe (Inno) or the entire dist\Camxora folder."
Write-Host "  Tip: rebuilds keep build/ cache; use -Clean only when packaging looks stale."
