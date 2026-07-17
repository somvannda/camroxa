param(
    [Parameter(Mandatory = $false)]
    [switch]$SkipVcRedist,

    [Parameter(Mandatory = $false)]
    [switch]$SkipFfmpeg,

    [Parameter(Mandatory = $false)]
    [string]$FfmpegBinDir = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Vendor = Join-Path $Root "vendor"
$FfmpegDir = Join-Path $Vendor "ffmpeg"
$VcDir = Join-Path $Vendor "vcredist"

New-Item -ItemType Directory -Force -Path $FfmpegDir | Out-Null
New-Item -ItemType Directory -Force -Path $VcDir | Out-Null

function Get-FileOrDownload([string]$Url, [string]$OutFile, [long]$MinBytes = 0) {
    $needsDownload = -not (Test-Path $OutFile)
    if (-not $needsDownload -and $MinBytes -gt 0) {
        $size = (Get-Item $OutFile).Length
        if ($size -lt $MinBytes) {
            Write-Host "Incomplete download ($size bytes), re-fetching: $OutFile"
            Remove-Item $OutFile -Force
            $needsDownload = $true
        }
    }
    if (-not $needsDownload) {
        Write-Host "Already present: $OutFile"
        return
    }
    Write-Host "Downloading $Url"
    Invoke-WebRequest -Uri $Url -OutFile $OutFile -UseBasicParsing
}

function Resolve-LocalFfmpegBin {
    param([string]$Preferred)
    $candidates = @()
    if ($Preferred) { $candidates += $Preferred }
    if ($env:CAMXORA_FFMPEG_BIN) { $candidates += $env:CAMXORA_FFMPEG_BIN }
    $candidates += @(
        "C:\ffmpeg\ffmpeg\ffmpeg-8.1-essentials_build\bin",
        "C:\ffmpeg\bin",
        "C:\Program Files\ffmpeg\bin"
    )
    foreach ($dir in $candidates) {
        if (-not $dir) { continue }
        $ff = Join-Path $dir "ffmpeg.exe"
        $fp = Join-Path $dir "ffprobe.exe"
        if ((Test-Path $ff) -and (Test-Path $fp)) {
            return (Resolve-Path $dir).Path
        }
    }
    return $null
}

if (-not $SkipFfmpeg) {
    $ffmpegExe = Join-Path $FfmpegDir "ffmpeg.exe"
    $ffprobeExe = Join-Path $FfmpegDir "ffprobe.exe"
    if (-not (Test-Path $ffmpegExe) -or -not (Test-Path $ffprobeExe)) {
        $localBin = Resolve-LocalFfmpegBin -Preferred $FfmpegBinDir
        if ($localBin) {
            Copy-Item (Join-Path $localBin "ffmpeg.exe") $ffmpegExe -Force
            Copy-Item (Join-Path $localBin "ffprobe.exe") $ffprobeExe -Force
            Write-Host "Copied local FFmpeg from $localBin into $FfmpegDir"
        } else {
            $zipPath = Join-Path $env:TEMP "ffmpeg-release-essentials.zip"
            # Essentials builds are typically 80MB+; smaller files are usually corrupt/partial.
            Get-FileOrDownload "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip" $zipPath -MinBytes 40000000
            $extractRoot = Join-Path $env:TEMP "ffmpeg-essentials-extract"
            if (Test-Path $extractRoot) { Remove-Item -Recurse -Force $extractRoot }
            try {
                Expand-Archive -Path $zipPath -DestinationPath $extractRoot -Force
            } catch {
                Write-Host "Corrupt FFmpeg ZIP, re-downloading..."
                Remove-Item $zipPath -Force -ErrorAction SilentlyContinue
                Get-FileOrDownload "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip" $zipPath -MinBytes 40000000
                if (Test-Path $extractRoot) { Remove-Item -Recurse -Force $extractRoot }
                Expand-Archive -Path $zipPath -DestinationPath $extractRoot -Force
            }
            $binDir = Get-ChildItem -Path $extractRoot -Recurse -Directory -Filter "bin" |
                Where-Object { Test-Path (Join-Path $_.FullName "ffmpeg.exe") } |
                Select-Object -First 1
            if (-not $binDir) {
                throw "Could not find ffmpeg.exe inside essentials ZIP"
            }
            Copy-Item (Join-Path $binDir.FullName "ffmpeg.exe") $ffmpegExe -Force
            Copy-Item (Join-Path $binDir.FullName "ffprobe.exe") $ffprobeExe -Force
            Write-Host "Bundled FFmpeg into $FfmpegDir"
        }
    } else {
        Write-Host "FFmpeg already bundled in $FfmpegDir"
    }
}

if (-not $SkipVcRedist) {
    $vcOut = Join-Path $VcDir "vc_redist.x64.exe"
    Get-FileOrDownload "https://aka.ms/vs/17/release/vc_redist.x64.exe" $vcOut
}

Write-Host "Installer assets ready under $Vendor"
