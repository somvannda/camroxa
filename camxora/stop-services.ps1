$ErrorActionPreference = "Stop"

$camxoraRoot = $PSScriptRoot
$stateFile = Join-Path $camxoraRoot ".dev-services.json"
$legacyPidFile = Join-Path $camxoraRoot ".dev-pids"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " CAMXORA Stop Services" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

function Stop-ProcessTree([int]$processId) {
  Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object { $_.ParentProcessId -eq $processId } |
    ForEach-Object { Stop-ProcessTree $_.ProcessId }
  Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
}

function Read-ServiceState {
  if (-not (Test-Path $stateFile)) {
    return $null
  }

  try {
    return Get-Content $stateFile -Raw | ConvertFrom-Json
  } catch {
    return $null
  }
}

function Remove-StateFiles {
  Remove-Item $stateFile -Force -ErrorAction SilentlyContinue
  Remove-Item $legacyPidFile -Force -ErrorAction SilentlyContinue
}

function Stop-PortProcesses([int[]] $ports) {
  foreach ($port in $ports) {
    $owners = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue |
      Select-Object -ExpandProperty OwningProcess -Unique

    foreach ($ownerId in $owners) {
      if (-not $ownerId -or [int]$ownerId -le 0) {
        continue
      }
      if ($ownerId -and (Get-Process -Id $ownerId -ErrorAction SilentlyContinue)) {
        Write-Host "  Killing PID $ownerId on port $port" -ForegroundColor DarkGray
        Stop-ProcessTree ([int]$ownerId)
      }
    }
  }
}

$state = Read-ServiceState
if ($null -eq $state) {
  if (Test-Path $legacyPidFile) {
    Write-Host "Stopping legacy PID file processes..." -ForegroundColor Yellow
    $legacyPids = Get-Content $legacyPidFile -ErrorAction SilentlyContinue
    foreach ($legacyProcessId in $legacyPids) {
      if ($legacyProcessId -and (Get-Process -Id $legacyProcessId -ErrorAction SilentlyContinue)) {
        Write-Host "  Stopping legacy PID $legacyProcessId" -ForegroundColor Gray
        Stop-ProcessTree ([int]$legacyProcessId)
      }
    }
    Remove-StateFiles
    Write-Host ""
    Write-Host "Done." -ForegroundColor Green
    exit 0
  }

  Write-Host "No owned CAMXORA service state found." -ForegroundColor Yellow
  exit 0
}

foreach ($entry in @(
    @{ Name = "API"; Pid = $state.apiShellPid },
    @{ Name = "Admin Portal"; Pid = $state.portalShellPid },
    @{ Name = "Website"; Pid = $state.websiteShellPid },
    @{ Name = "User Portal"; Pid = $state.userPortalShellPid },
    @{ Name = "Music Web"; Pid = $state.musicWebShellPid }
  )) {
  if ($entry.Pid -and (Get-Process -Id $entry.Pid -ErrorAction SilentlyContinue)) {
    Write-Host "  Stopping $($entry.Name) PID $($entry.Pid)" -ForegroundColor Gray
    Stop-ProcessTree ([int]$entry.Pid)
  }
}

Write-Host "  Checking owned development ports (8000, 5173, 3000, 3001, 3003)..." -ForegroundColor Gray
Stop-PortProcesses -ports @(8000, 5173, 3000, 3001, 3003)

if ($state.mailhogStartedByScript -and $state.mailhogPid) {
  if (Get-Process -Id $state.mailhogPid -ErrorAction SilentlyContinue) {
    Write-Host "  Stopping MailHog PID $($state.mailhogPid)" -ForegroundColor Gray
    Stop-ProcessTree ([int]$state.mailhogPid)
  }
} elseif ($state.mailhogPid) {
  Write-Host "  Leaving existing MailHog running (PID $($state.mailhogPid))" -ForegroundColor DarkGray
}

Remove-StateFiles

Write-Host ""
Write-Host "Done. Owned CAMXORA services stopped." -ForegroundColor Green
