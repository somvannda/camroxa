$ErrorActionPreference = "Stop"

$camxoraRoot = $PSScriptRoot
$repoRoot = Resolve-Path (Join-Path $camxoraRoot "..")
$stateFile = Join-Path $camxoraRoot ".dev-services.json"
$legacyPidFile = Join-Path $camxoraRoot ".dev-pids"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " CAMXORA Dev Services" -ForegroundColor Cyan
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

function Write-ServiceState([hashtable]$state) {
  $state | ConvertTo-Json -Depth 5 | Set-Content -Path $stateFile
}

function Remove-ServiceStateFiles {
  Remove-Item $stateFile -Force -ErrorAction SilentlyContinue
  Remove-Item $legacyPidFile -Force -ErrorAction SilentlyContinue
}

function Stop-OwnedServices {
  $state = Read-ServiceState
  if ($null -eq $state) {
    if (Test-Path $legacyPidFile) {
      $oldPids = Get-Content $legacyPidFile -ErrorAction SilentlyContinue
      foreach ($oldProcessId in $oldPids) {
        if ($oldProcessId -and (Get-Process -Id $oldProcessId -ErrorAction SilentlyContinue)) {
          Write-Host "  Stopping legacy PID $oldProcessId" -ForegroundColor Gray
          Stop-ProcessTree ([int]$oldProcessId)
        }
      }
      Remove-ServiceStateFiles
    }
    return
  }

  foreach ($key in @("apiShellPid", "portalShellPid", "websiteShellPid", "userPortalShellPid", "musicWebShellPid")) {
    $ownedProcessId = $state.$key
    if ($ownedProcessId -and (Get-Process -Id $ownedProcessId -ErrorAction SilentlyContinue)) {
      Write-Host "  Stopping $key PID $ownedProcessId" -ForegroundColor Gray
      Stop-ProcessTree ([int]$ownedProcessId)
    }
  }

  if ($state.mailhogStartedByScript -and $state.mailhogPid) {
    if (Get-Process -Id $state.mailhogPid -ErrorAction SilentlyContinue) {
      Write-Host "  Stopping MailHog PID $($state.mailhogPid)" -ForegroundColor Gray
      Stop-ProcessTree ([int]$state.mailhogPid)
    }
  }

  Remove-ServiceStateFiles
}

function Stop-PortProcesses([int[]] $ports) {
  foreach ($port in $ports) {
    $procs = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue |
      Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($portOwnerId in $procs) {
      if (-not $portOwnerId -or [int]$portOwnerId -le 0) {
        continue
      }
      Write-Host "  Killing PID $portOwnerId on port $port" -ForegroundColor Gray
      Stop-ProcessTree ([int]$portOwnerId)
    }
  }
}

function Get-PortOwners([int[]] $ports) {
  $result = @{}
  foreach ($port in $ports) {
    $owners = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue |
      Select-Object -ExpandProperty OwningProcess -Unique
    $result[$port] = @($owners | Where-Object { $_ -and [int]$_ -gt 0 })
  }
  return $result
}

function Get-MailHogExecutablePath {
  $candidates = @()

  if ($env:MAILHOG_EXE) {
    $candidates += $env:MAILHOG_EXE
  }

  $candidates += @(
    (Join-Path $repoRoot "tools\mailhog.exe"),
    (Join-Path $repoRoot "mailhog.exe"),
    "D:\Development\Chmaba\mailhog.exe"
  )

  foreach ($candidate in $candidates) {
    if ($candidate -and (Test-Path $candidate)) {
      return (Resolve-Path $candidate).Path
    }
  }

  return $null
}

function Get-ExistingMailHogInfo([string]$mailhogExePath) {
  $ownersByPort = Get-PortOwners -ports @(1025, 8025)
  $smtpOwners = @($ownersByPort[1025])
  $uiOwners = @($ownersByPort[8025])

  if ($smtpOwners.Count -eq 0 -and $uiOwners.Count -eq 0) {
    return $null
  }

  $uniqueOwners = @($smtpOwners + $uiOwners | Sort-Object -Unique)
  if ($uniqueOwners.Count -ne 1) {
    throw "Ports 1025 and 8025 are not owned by the same process. Fix MailHog ports before starting CAMXORA services."
  }

  $mailhogProcessId = [int]$uniqueOwners[0]
  $process = Get-CimInstance Win32_Process -Filter "ProcessId = $mailhogProcessId" -ErrorAction SilentlyContinue
  if ($null -eq $process) {
    throw "Unable to inspect the process currently using MailHog ports."
  }

  $expectedName = if ($mailhogExePath) { [System.IO.Path]::GetFileNameWithoutExtension($mailhogExePath) } else { "mailhog" }
  $actualName = [System.IO.Path]::GetFileNameWithoutExtension([string]$process.Name)
  $actualPath = [string]$process.ExecutablePath

  $looksLikeMailHog = $actualName -ieq $expectedName -or $actualName -ieq "mailhog" -or ($actualPath -and $actualPath -ieq $mailhogExePath)
  if (-not $looksLikeMailHog) {
    throw "Ports 1025/8025 are already in use by '$($process.Name)'. Please free those ports or start MailHog manually before running this script."
  }

  return @{
    pid = $mailhogProcessId
    reused = $true
  }
}

function Ensure-MailHog {
  $mailhogExe = Get-MailHogExecutablePath
  if (-not $mailhogExe) {
    throw "MailHog executable not found. Set MAILHOG_EXE or place mailhog.exe in a known path."
  }

  $existing = Get-ExistingMailHogInfo -mailhogExePath $mailhogExe
  if ($existing) {
    Write-Host "  MailHog: reusing existing process on 1025/8025 (PID $($existing.pid))" -ForegroundColor Green
    return @{
      pid = $existing.pid
      startedByScript = $false
      smtpUrl = "smtp://localhost:1025"
      uiUrl = "http://localhost:8025"
    }
  }

  Write-Host "  MailHog: starting..." -ForegroundColor Yellow
  $mailhogProc = Start-Process -FilePath $mailhogExe -WorkingDirectory (Split-Path $mailhogExe -Parent) -PassThru -WindowStyle Hidden
  Start-Sleep -Seconds 1

  return @{
    pid = $mailhogProc.Id
    startedByScript = $true
    smtpUrl = "smtp://localhost:1025"
    uiUrl = "http://localhost:8025"
  }
}

Write-Host "[CLEANUP] Checking for leftover processes..." -ForegroundColor Yellow
Stop-OwnedServices
Stop-PortProcesses -ports @(8000, 5173, 3000, 3001, 3003)
Start-Sleep -Seconds 1

Write-Host ""
Write-Host "[CHECK] Prerequisites" -ForegroundColor Yellow
try {
  $pythonVersion = & python --version 2>&1
  Write-Host "  Python: $pythonVersion" -ForegroundColor Gray
} catch {
  Write-Host "  Python: NOT FOUND" -ForegroundColor Red
  throw
}

$mailhogInfo = Ensure-MailHog

Write-Host ""
Write-Host "Starting services (separate PowerShell windows)..." -ForegroundColor Cyan
Write-Host ""

$apiCommand = @"
`$env:PYTHONPATH = '$repoRoot'
cd '$repoRoot'
python -u -m uvicorn platform_api.main:app --reload --reload-dir platform_api --host 0.0.0.0 --port 8000 --log-config platform_api/log_config.json --log-level info
"@

$adminCommand = @"
cd '$repoRoot\admin_portal'
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
"@

$websiteCommand = @"
cd '$repoRoot\website'
npm run dev -- --hostname 127.0.0.1 --port 3000
"@

$userPortalCommand = @"
cd '$repoRoot\user_portal'
npm run dev -- --hostname 127.0.0.1 --port 3001
"@

$musicWebCommand = @"
cd '$repoRoot\music_web'
npm run dev -- --hostname 127.0.0.1 --port 3003
"@

$apiProc = Start-Process -FilePath "powershell" -ArgumentList "-NoExit", "-Command", $apiCommand -PassThru
$portalProc = Start-Process -FilePath "powershell" -ArgumentList "-NoExit", "-Command", $adminCommand -PassThru
$websiteProc = Start-Process -FilePath "powershell" -ArgumentList "-NoExit", "-Command", $websiteCommand -PassThru
$userPortalProc = Start-Process -FilePath "powershell" -ArgumentList "-NoExit", "-Command", $userPortalCommand -PassThru
$musicWebProc = Start-Process -FilePath "powershell" -ArgumentList "-NoExit", "-Command", $musicWebCommand -PassThru

Write-ServiceState @{
  apiShellPid = $apiProc.Id
  portalShellPid = $portalProc.Id
  websiteShellPid = $websiteProc.Id
  userPortalShellPid = $userPortalProc.Id
  musicWebShellPid = $musicWebProc.Id
  mailhogPid = $mailhogInfo.pid
  mailhogStartedByScript = $mailhogInfo.startedByScript
  startedAt = (Get-Date).ToString("o")
}

Write-Host "========================================" -ForegroundColor Green
Write-Host " Services started" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "  API:          http://localhost:8000" -ForegroundColor Gray
Write-Host "  Admin Portal: http://localhost:5173" -ForegroundColor Gray
Write-Host "  Website:      http://localhost:3000" -ForegroundColor Gray
Write-Host "  User Portal:  http://localhost:3001" -ForegroundColor Gray
Write-Host "  Music Web:    http://localhost:3003" -ForegroundColor Gray
Write-Host "  MailHog UI:   $($mailhogInfo.uiUrl)" -ForegroundColor Gray
Write-Host "  MailHog SMTP: $($mailhogInfo.smtpUrl)" -ForegroundColor Gray
Write-Host ""
Write-Host "To stop everything cleanly: run .\stop-services.ps1" -ForegroundColor Yellow
