# ─────────────────────────────────────────────────────────────────────────────
# setup-db.ps1 — Create the database and run all migrations from scratch
#
# Usage (on a fresh machine after git clone):
#   cd platform_api
#   pip install -e ".[dev]"
#   .\setup-db.ps1
#
# This will:
#   1. Create the 'platform_db' database if it doesn't exist
#   2. Run all Alembic migrations to bring schema to latest
#
# Prerequisites:
#   - PostgreSQL installed and running on localhost:5432
#   - User 'postgres' accessible (or set $env:DB_USER)
#   - Python environment with platform_api[dev] installed
# ─────────────────────────────────────────────────────────────────────────────

$ErrorActionPreference = "Stop"

$ScriptDir = $PSScriptRoot
$ProjectRoot = Split-Path $ScriptDir -Parent

$env:PYTHONPATH = $ProjectRoot

$DB_USER = if ($env:DB_USER) { $env:DB_USER } else { "postgres" }
$DB_NAME = if ($env:DB_NAME) { $env:DB_NAME } else { "platform_db" }
$DB_HOST = if ($env:DB_HOST) { $env:DB_HOST } else { "localhost" }
$DB_PORT = if ($env:DB_PORT) { $env:DB_PORT } else { "5432" }

# Find psql
$psqlPath = $null
$pgPaths = @(
    "C:\Program Files\PostgreSQL\16\bin\psql.exe",
    "C:\Program Files\PostgreSQL\15\bin\psql.exe",
    "C:\Program Files\PostgreSQL\14\bin\psql.exe"
)
foreach ($p in $pgPaths) {
    if (Test-Path $p) { $psqlPath = $p; break }
}
if (-not $psqlPath) {
    $psqlPath = Get-Command psql -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source
}
if (-not $psqlPath) {
    Write-Host "ERROR: psql not found. Install PostgreSQL or add it to PATH." -ForegroundColor Red
    exit 1
}
$pgBinDir = Split-Path $psqlPath -Parent

Set-Location $ScriptDir

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host " CAMXORA Database Setup" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

# Check PostgreSQL is running
$pgRunning = Get-NetTCPConnection -LocalPort $DB_PORT -ErrorAction SilentlyContinue
if (-not $pgRunning) {
    Write-Host "ERROR: PostgreSQL is not running on ${DB_HOST}:${DB_PORT}" -ForegroundColor Red
    Write-Host "  Start it first, then re-run this script." -ForegroundColor Gray
    exit 1
}
Write-Host "OK PostgreSQL is running on ${DB_HOST}:${DB_PORT}" -ForegroundColor Green

# Create database if it doesn't exist
$env:PGPASSWORD = $DB_USER
$dbExists = & $psqlPath -h $DB_HOST -p $DB_PORT -U $DB_USER -lqt 2>$null | Select-String "^\s*$DB_NAME\s*\|"
if ($dbExists) {
    Write-Host "OK Database '$DB_NAME' already exists" -ForegroundColor Green
} else {
    Write-Host "Creating database '$DB_NAME'..." -ForegroundColor Yellow
    $createDbPath = Join-Path $pgBinDir "createdb.exe"
    & $createDbPath -h $DB_HOST -p $DB_PORT -U $DB_USER $DB_NAME
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to create database" -ForegroundColor Red
        exit 1
    }
    Write-Host "OK Database '$DB_NAME' created" -ForegroundColor Green
}

# Check if .env exists
$envFile = Join-Path $ScriptDir ".env"
if (-not (Test-Path $envFile)) {
    Write-Host ""
    Write-Host "WARNING: No .env file found. Creating default..." -ForegroundColor Yellow
    @"
PLATFORM_DEBUG=true
PLATFORM_DATABASE_URL=postgresql+asyncpg://${DB_USER}:${DB_USER}@${DB_HOST}:${DB_PORT}/${DB_NAME}
PLATFORM_REDIS_URL=redis://localhost:6379/0
PLATFORM_ENCRYPTION_MASTER_KEY=OK_LET_DO_THIS
PLATFORM_SLAI_API_BASE_URL=https://api.slai.shop
PLATFORM_DEEPSEEK_API_BASE_URL=https://api.deepseek.com
"@ | Set-Content $envFile -Encoding utf8
    Write-Host "OK Default .env created" -ForegroundColor Green
}

# Run migrations
Write-Host ""
Write-Host "Running all migrations..." -ForegroundColor Yellow
& alembic upgrade head
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Alembic migration failed" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=========================================" -ForegroundColor Green
Write-Host " Database setup complete!" -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Current migration version:" -ForegroundColor Gray
& alembic current
Write-Host ""
Write-Host "You can now start the API with:" -ForegroundColor Gray
Write-Host "  uvicorn platform_api.main:app --reload --host 0.0.0.0 --port 8000" -ForegroundColor Gray
