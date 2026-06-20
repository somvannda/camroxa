# stop-dev.ps1
# Stops all dev services started by start-dev.ps1
# Usage: .\stop-dev.ps1

$root = $PSScriptRoot
$pidFile = Join-Path $root ".dev-pids"

Write-Host "Stopping dev services..." -ForegroundColor Yellow

function Stop-ProcessTree($processId) {
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object { $_.ParentProcessId -eq $processId } |
        ForEach-Object { Stop-ProcessTree $_.ProcessId }
    Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
}

# Kill saved PIDs
if (Test-Path $pidFile) {
    $pids = Get-Content $pidFile
    foreach ($p in $pids) {
        if ($p -and (Get-Process -Id $p -ErrorAction SilentlyContinue)) {
            Write-Host "  Stopping PID $p (+ children)..." -ForegroundColor Gray
            Stop-ProcessTree ([int]$p)
        }
    }
    Remove-Item $pidFile -Force
} else {
    Write-Host "  No PID file found. Killing by port..." -ForegroundColor Gray
}

# Kill anything still on our ports (catches orphans)
foreach ($port in @(8000, 5173, 8025, 1025)) {
    $procs = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($p in $procs) {
        Write-Host "  Killing PID $p on port $port" -ForegroundColor Gray
        Stop-ProcessTree $p
    }
}

Write-Host ""
Write-Host "Done. All services stopped." -ForegroundColor Green
Write-Host ""
Write-Host "Note: PostgreSQL and Redis are Windows services and were NOT stopped." -ForegroundColor DarkGray
