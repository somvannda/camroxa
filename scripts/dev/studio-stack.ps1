# Studio dev stack: moto storage + platform API with the Studio token.
#
# Why this exists: a restart of platform_api without PLATFORM_STUDIO_INTERNAL_TOKEN
# silently disables every Studio clip operation, and without an explicit
# PLATFORM_DATABASE_URL it connects to platform_db instead of the sandbox. See README.md.
#
# Usage:
#   $env:PLATFORM_STUDIO_INTERNAL_TOKEN = "<value musicapi runs with>"
#   pwsh -File scripts/dev/studio-stack.ps1 [-DryRun] [-Stop]
param(
    [switch]$DryRun,
    [switch]$Stop,
    [switch]$Status,
    [switch]$All,
    [string]$Token = $env:PLATFORM_STUDIO_INTERNAL_TOKEN,
    [string]$DatabaseUrl = "postgresql+asyncpg://postgres:postgres@localhost:5432/camxora_pfm_sandbox",
    [string]$EnvFile = "G:\Developments\Projects\Camxora\platform_api\.env",
    [int]$ApiPort = 8100,
    [int]$MotoPort = 9000,
    [int]$MusicPort = 4003,
    [int]$WebPort = 3103
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")

function Get-PortOwner([int]$port) {
    Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
}

function Stop-Port([int]$port, [string]$label) {
    $owners = Get-PortOwner $port
    if (-not $owners) {
        Write-Host "$label ($port) is not running."
        return
    }
    foreach ($owner in $owners) {
        Write-Host "Stopping $label (pid $owner) on port $port..."
        if (-not $DryRun) { Stop-Process -Id $owner -Force }
    }
}

if ($Stop) {
    Stop-Port $ApiPort "platform API"
    Stop-Port $MotoPort "moto"
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like "*run-platform-worker*" } |
        ForEach-Object {
            Write-Host "Stopping platform worker (pid $($_.ProcessId))..."
            if (-not $DryRun) { Stop-Process -Id $_.ProcessId -Force }
        }
    if ($All) {
        Stop-Port $MusicPort "musicapi"
        Stop-Port $WebPort "web"
    }
    return
}

function Get-Health([int]$port, [string]$path = "/health") {
    try {
        $response = Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$port$path" -TimeoutSec 10
        return "up ($($response.StatusCode))"
    } catch {
        if (Get-PortOwner $port) { return "listening, health failed" }
        return "down"
    }
}

if ($Status) {
    Write-Host "web        :$WebPort      $(Get-Health $WebPort '/library')"
    Write-Host "platform   :$ApiPort      $(Get-Health $ApiPort)"
    Write-Host "musicapi   :$MusicPort    $(Get-Health $MusicPort)"
    Write-Host "moto       :$MotoPort     $(if (Get-PortOwner $MotoPort) { 'listening' } else { 'down' })"
    return
}

if (-not $Token) {
    throw "PLATFORM_STUDIO_INTERNAL_TOKEN is empty. Export the value musicapi uses (see scripts/dev/README.md) so Studio clip operations stay enabled."
}

$motoEnv = @{
    PLATFORM_STREAMING_B2_KEY_ID          = "minioadmin"
    PLATFORM_STREAMING_B2_APPLICATION_KEY = "minioadmin"
    PLATFORM_STREAMING_B2_BUCKET          = "camxora-studio"
    PLATFORM_STREAMING_B2_REGION          = "us-east-1"
    PLATFORM_STREAMING_B2_ENDPOINT        = "http://127.0.0.1:$MotoPort"
}

$apiEnv = @{
    PYTHONIOENCODING               = "utf-8"
    PLATFORM_DATABASE_URL          = $DatabaseUrl
    PLATFORM_CREDITS_ONLY_V3_CHARGE = "true"
    PLATFORM_STUDIO_INTERNAL_TOKEN = $Token
} + $motoEnv

# Optional: route Suno provider calls at a local musicapi (matched pool keys carry the
# same base_url). Without it the client uses PLATFORM_SUNO_API_BASE_URL from the env file.
if ($env:PLATFORM_SUNO_API_BASE_URL) {
    $apiEnv["PLATFORM_SUNO_API_BASE_URL"] = $env:PLATFORM_SUNO_API_BASE_URL
}

# A local musicapi rejects localhost callback URLs, so pointing Suno provider calls at
# 127.0.0.1:4003 also needs a public callback host (e.g. a cloudflared quick tunnel to
# :8100). Pass it the same way; without it the client sends https://localhost/... and
# musicapi answers 400 "callback_url must not target a local host".
if ($env:PLATFORM_SUNO_CALLBACK_BASE_URL) {
    $apiEnv["PLATFORM_SUNO_CALLBACK_BASE_URL"] = $env:PLATFORM_SUNO_CALLBACK_BASE_URL
}

if ($DryRun) {
    Write-Host "Dry run - would start:"
    Write-Host "  moto server on :$MotoPort"
    Write-Host "  bucket camxora-studio"
    Write-Host "  uvicorn platform_api.main:app on :$ApiPort"
    Write-Host "  database: $DatabaseUrl"
    Write-Host "  env file: $EnvFile"
    Write-Host "  token: set ($($Token.Length) characters)"
    if ($All) {
        Write-Host "  musicapi on :$MusicPort (build if dist is missing)"
        Write-Host "  web dev server on :$WebPort"
    }
    return
}

Push-Location $root
try {
    if (-not (Get-PortOwner $MotoPort)) {
        Write-Host "Starting moto on :$MotoPort..."
        Start-Process -FilePath "python" -ArgumentList @("-m", "moto.server", "-p", "$MotoPort") `
            -WorkingDirectory $root -WindowStyle Hidden
        Start-Sleep -Seconds 3
    } else {
        Write-Host "moto already listening on :$MotoPort."
    }

    $bucketScript = "import boto3`ntry:`n    boto3.client('s3', endpoint_url='http://127.0.0.1:$MotoPort', aws_access_key_id='minioadmin', aws_secret_access_key='minioadmin', region_name='us-east-1').create_bucket(Bucket='camxora-studio')`n    print('bucket created')`nexcept Exception:`n    print('bucket ready')"
    python -c $bucketScript
    if ($LASTEXITCODE -ne 0) { throw "Could not prepare the moto bucket." }

    if (Get-PortOwner $ApiPort) {
        throw "Port $ApiPort is already in use. Stop the running platform API first (or pass -Stop), so the Studio token cannot be lost silently."
    }

    if ($All) {
        if (-not (Get-PortOwner $MusicPort)) {
            $music = Join-Path $root "musicapi"
            if (-not (Test-Path (Join-Path $music "dist\serve.js"))) {
                Write-Host "Building musicapi..."
                Push-Location $music
                npm run build
                Pop-Location
            }
            Write-Host "Starting musicapi on :$MusicPort..."
            Start-Process -FilePath "npm.cmd" -ArgumentList @("run", "start") -WorkingDirectory $music -WindowStyle Hidden
            Start-Sleep -Seconds 4
        } else {
            Write-Host "musicapi already listening on :$MusicPort."
        }

        if (-not (Get-PortOwner $WebPort)) {
            Write-Host "Starting web dev server on :$WebPort..."
            Start-Process -FilePath "npm.cmd" -ArgumentList @("run", "dev") -WorkingDirectory (Join-Path $root "camxora.com") -WindowStyle Hidden
        } else {
            Write-Host "web already listening on :$WebPort."
        }
    }

    foreach ($key in $apiEnv.Keys) { Set-Item -Path "Env:$key" -Value $apiEnv[$key] }
    $apiLog = Join-Path $env:TEMP "camxora-platform-api.out.log"
    $apiErr = Join-Path $env:TEMP "camxora-platform-api.err.log"
    Write-Host "Starting platform API on :$ApiPort (sandbox DB, Studio token set; logs: $apiLog)..."
    # Redirect stdio: without it the child keeps the caller's console handles open and a
    # non-interactive `powershell -File studio-stack.ps1` never returns.
    Start-Process -FilePath "python" `
        -ArgumentList @("-m", "uvicorn", "platform_api.main:app", "--host", "127.0.0.1", "--port", "$ApiPort", "--env-file", $EnvFile, "--log-level", "warning") `
        -WorkingDirectory $root -RedirectStandardOutput $apiLog -RedirectStandardError $apiErr -WindowStyle Hidden

    Start-Sleep -Seconds 12
    try {
        $health = Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$ApiPort/health" -TimeoutSec 60
        Write-Host "platform API health: $($health.StatusCode)"
    } catch {
        Write-Warning "API did not answer /health yet: $($_.Exception.Message). Check its window for migration output."
    }

    # Generation jobs sit in `job_queue` until this worker drains them. It is not needed
    # for the editor or exports, but without it "/create" generations stay pending — and
    # without rows in `api_key_entries` for the provider the worker fails with
    # "No available API keys for provider 'suno'".
    $workerLog = Join-Path $env:TEMP "camxora-platform-worker.out.log"
    $workerErr = Join-Path $env:TEMP "camxora-platform-worker.err.log"
    Write-Host "Starting platform worker (logs: $workerLog)..."
    # The worker must read the same env file as the API (master key, provider secrets).
    Set-Item -Path "Env:PLATFORM_ENV_FILE" -Value $EnvFile
    Start-Process -FilePath "python" -ArgumentList @("scripts/dev/run-platform-worker.py") `
        -WorkingDirectory $root -RedirectStandardOutput $workerLog -RedirectStandardError $workerErr -WindowStyle Hidden
} finally {
    Pop-Location
}
