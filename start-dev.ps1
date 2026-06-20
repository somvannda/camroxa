# start-dev.ps1
# Starts all dev services in a single terminal window
# Usage: .\start-dev.ps1

$root = $PSScriptRoot
$pidFile = Join-Path $root ".dev-pids"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " CAMXORA Dev Environment" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Kill leftover processes from previous runs
Write-Host "[CLEANUP] Checking for leftover processes..." -ForegroundColor Yellow
if (Test-Path $pidFile) {
    $oldPids = Get-Content $pidFile
    foreach ($p in $oldPids) {
        if ($p -and (Get-Process -Id $p -ErrorAction SilentlyContinue)) {
            Write-Host "  Killing leftover PID $p" -ForegroundColor Gray
            Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
        }
    }
    Remove-Item $pidFile -Force
}

# Kill anything on our ports
foreach ($port in @(8000, 5173, 8025, 1025)) {
    $procs = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($p in $procs) {
        Write-Host "  Killing PID $p on port $port" -ForegroundColor Gray
        Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
    }
}
Start-Sleep -Seconds 1

# Verify prerequisites
Write-Host ""
Write-Host "[CHECK] Prerequisites" -ForegroundColor Yellow
$pythonVersion = & python --version 2>&1
Write-Host "  Python: $pythonVersion" -ForegroundColor Gray

$envFile = Join-Path $root "platform_api\.env"
if (Test-Path $envFile) { Write-Host "  .env: EXISTS" -ForegroundColor Green } else { Write-Host "  .env: MISSING" -ForegroundColor Red }

# Check infrastructure
$pg = Get-NetTCPConnection -LocalPort 5432 -ErrorAction SilentlyContinue
$redis = Get-NetTCPConnection -LocalPort 6379 -ErrorAction SilentlyContinue
if ($pg) { Write-Host "  PostgreSQL: RUNNING" -ForegroundColor Green } else { Write-Host "  PostgreSQL: NOT RUNNING" -ForegroundColor Red }
if ($redis) { Write-Host "  Redis: RUNNING" -ForegroundColor Green } else { Write-Host "  Redis: NOT RUNNING" -ForegroundColor Red }

# Start MailHog if not running
$mailhogExe = "D:\Development\Chmaba\mailhog.exe"
$mailhogRunning = Get-NetTCPConnection -LocalPort 8025 -ErrorAction SilentlyContinue
if (-not $mailhogRunning -and (Test-Path $mailhogExe)) {
    Write-Host "  MailHog: Starting..." -ForegroundColor Yellow
    Start-Process -FilePath $mailhogExe -WindowStyle Hidden | Out-Null
    Start-Sleep -Seconds 1
}

Write-Host ""
Write-Host "Starting services..." -ForegroundColor Cyan
Write-Host ""

# Start Platform API
$env:PYTHONPATH = $root
$apiProc = Start-Process -FilePath "python" `
    -ArgumentList "-u", "-m", "uvicorn", "platform_api.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info" `
    -WorkingDirectory $root `
    -NoNewWindow -PassThru

# Start Admin Portal
$portalProc = Start-Process -FilePath "cmd.exe" `
    -ArgumentList "/c", "npm run dev" `
    -WorkingDirectory (Join-Path $root "admin_portal") `
    -NoNewWindow -PassThru

# Save PIDs
@($apiProc.Id, $portalProc.Id) | Set-Content $pidFile

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " All services running in this window" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "  API:    http://localhost:8000" -ForegroundColor Gray
Write-Host "  Portal: http://localhost:5173" -ForegroundColor Gray
Write-Host "  MailHog: http://localhost:8025" -ForegroundColor Gray
Write-Host ""
Write-Host "Press Ctrl+C to stop all services." -ForegroundColor Yellow
