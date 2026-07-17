import { app, BrowserWindow, dialog, ipcMain, safeStorage, screen, shell } from 'electron'
import path from 'node:path'
import fs from 'node:fs'
import os from 'node:os'
import https from 'node:https'
import http from 'node:http'
import crypto from 'node:crypto'
import { URL } from 'node:url'
import { spawn } from 'node:child_process'
import {
  activateEffectPackVersion,
  installEffectPackFromFile,
  installEffectPackFromUrl,
  listEffectPackCatalog,
  removeEffectPack,
  setEffectPackEnabled,
} from './effectPackRegistry'

type SecureRecord = Record<string, string>
type VideoWorkspacePrefs = {
  templateId?: string | null
  outputResolution?: string
  backgroundPath?: string
  logoPath?: string
  selectedMp3Path?: string
}
type VideoTemplateRecord = {
  id: string
  name: string
  source?: string
  updated_at?: string | null
  template?: Record<string, unknown>
}
type VideoWorkspaceState = {
  template: Record<string, unknown>
  templateId: string | null
  templateName: string
  templates: Array<{
    id: string
    name: string
    kind: string | null
    updatedAt: string | null
  }>
  outputResolution: string
  previewAspectRatio: {
    width: number
    height: number
  }
  backgroundPath: string
  logoPath: string
  selectedMp3Path: string
  mp3Directory: string
  mp3List: Array<{ name: string; path: string }>
  playback: {
    isPlaying: boolean
    isReady: boolean
    isLoading: boolean
    currentTimeSec: number
    durationSec: number
  }
  export: {
    running: boolean
    branch: 'long' | 'reel' | null
    workers: number
    autoMerge: boolean
    mergeRunning: boolean
    currentStatus: string
    outputDir: string | null
    currentOutputPath?: string | null
    totalJobs: number
    completedJobs: number
    progressPercent?: number
    estimatedRemainingSec?: number | null
    startedAtMs?: number | null
    lastOutputPath: string | null
    lastMergedOutputPath: string | null
  }
  ui: {
    previewTitle: string
    livePreviewOpen: boolean
    source: 'python-local' | 'fallback'
    notes: string[]
  }
}
type VideoExportBranch = 'long' | 'reel'
type VideoPipelineExportRequest = {
  runDir: string
  backgroundPath: string
  branch: VideoExportBranch
  batchId: string
  role: string
  /** Live Music/settings flags from renderer (preferred over hardcoded defaults). */
  settings?: Record<string, unknown> | null
  autoMerge?: boolean | null
}
type ManualVideoExportRequest = {
  scene: {
    mode: 'manual' | 'pipeline'
    template: Record<string, unknown>
    draft: Record<string, unknown>
    assets: {
      backgroundPath: string | null
      logoPath: string | null
      audioPath: string | null
      runDir: string | null
    }
    output: {
      resolution: string
      width: number
      height: number
      fps: number
    }
    context: {
      templateId: string | null
      branch: VideoExportBranch | null
      batchId: string | null
      role: string | null
      draftSource: 'live' | 'saved'
    }
  }
}
type VideoExportHostStatusPayload = {
  status: string
  message?: string
}
type VideoExportHostCommandPayload =
  | { type: 'play' }
  | { type: 'pause' }
  | { type: 'stop' }
  | { type: 'seek'; timeSec: number }
  | { type: 'capture-frame'; requestId: string; timeSec: number }
type VideoExportHostPlaybackPayload = {
  isPlaying: boolean
  isReady: boolean
  isLoading: boolean
  currentTimeSec: number
  durationSec: number
}
type VideoExportHostCaptureFramePayload = {
  requestId: string
  width: number
  height: number
  pixelData: Uint8Array
}
type PendingVideoExportHostCaptureRequest = {
  requestId: string
  resolve: (payload: VideoExportHostCaptureFramePayload) => void
  reject: (error: Error) => void
  timeoutId: ReturnType<typeof setTimeout>
}
type ActiveVideoExportState = {
  running: boolean
  branch: VideoExportBranch | null
  runDir: string | null
  outputDir: string | null
  currentOutputPath: string | null
  workers: number
  autoMerge: boolean
  mergeRunning: boolean
  currentStatus: string
  totalJobs: number
  completedJobs: number
  lastOutputPath: string | null
  lastMergedOutputPath: string | null
  startedAtMs: number | null
  lastProgressEventAtMs: number
  selectedMp3Path: string
  mp3List: Array<{ name: string; path: string }>
  queue: string[]
  activeJobs: Map<string, ReturnType<typeof spawn>>
  stopRequested: boolean
}
type MusicTrackDownloadRequest = {
  taskId: string
  channel: 'primary' | 'secondary'
  url: string
  outputDir: string
  targetPath: string
}
type MusicTrackDownloadResult = {
  taskId: string
  channel: 'primary' | 'secondary'
  ok: boolean
  outputDir: string | null
  targetPath: string | null
  skippedExisting: boolean
  error?: string
}

type VideoPreviewHostBounds = {
  x: number
  y: number
  width: number
  height: number
  dpr: number
}

type VideoPreviewEventPayload = {
  status: string
  message?: string
  preview?: {
    pid?: number
    hwnd?: number
    platform?: string
  }
}

type ActiveVideoPreviewState = {
  running: boolean
  embedded: boolean
  child: ReturnType<typeof spawn> | null
  bounds: VideoPreviewHostBounds | null
  currentEvent: VideoPreviewEventPayload | null
}
type ActiveVideoExportHostState = {
  ready: boolean
  pendingScene: ManualVideoExportRequest['scene'] | null
  currentStatus: VideoExportHostStatusPayload | null
  currentPlayback: VideoExportHostPlaybackPayload | null
  currentScene: ManualVideoExportRequest['scene'] | null
  captureProbeRunning: boolean
}

type VideoPyWorkspaceEventPayload = {
  status: string
  message?: string
  preview?: {
    pid?: number
    hwnd?: number
    platform?: string
  }
}
type ActiveVideoPyWorkspaceState = {
  running: boolean
  embedded: boolean
  child: ReturnType<typeof spawn> | null
  bounds: VideoPreviewHostBounds | null
  currentEvent: VideoPyWorkspaceEventPayload | null
}

const isDev = !app.isPackaged
const devServerUrl = process.env.CAMXORA_DEV_SERVER_URL ?? 'http://127.0.0.1:5174'
const secureStorePath = path.join(app.getPath('userData'), 'camxora-secure-store.json')
const videoWorkspacePrefsPath = path.join(app.getPath('userData'), 'camxora-video-workspace.json')
const videoAudioAnalysisCacheRoot = path.join(app.getPath('userData'), 'video-audio-analysis-cache')
const effectPackRegistryRoot = path.join(app.getPath('userData'), 'effect-packs')
const appIconPath = app.isPackaged
  ? path.join(process.resourcesPath, 'app.ico')
  : path.join(app.getAppPath(), 'public', 'app.ico')
const activeVideoExport: ActiveVideoExportState = {
  running: false,
  branch: null,
  runDir: null,
  outputDir: null,
  currentOutputPath: null,
  workers: 1,
  autoMerge: false,
  mergeRunning: false,
  currentStatus: 'Read-only bootstrap loaded from local Python template/settings sources.',
  totalJobs: 0,
  completedJobs: 0,
  lastOutputPath: null,
  lastMergedOutputPath: null,
  startedAtMs: null,
  lastProgressEventAtMs: 0,
  selectedMp3Path: '',
  mp3List: [],
  queue: [],
  activeJobs: new Map(),
  stopRequested: false,
}

const activeVideoPreview: ActiveVideoPreviewState = {
  running: false,
  embedded: false,
  child: null,
  bounds: null,
  currentEvent: null,
}

const activeVideoPyWorkspace: ActiveVideoPyWorkspaceState = {
  running: false,
  embedded: false,
  child: null,
  bounds: null,
  currentEvent: null,
}

const activeVideoExportHost: ActiveVideoExportHostState = {
  ready: false,
  pendingScene: null,
  currentStatus: null,
  currentPlayback: null,
  currentScene: null,
  captureProbeRunning: false,
}
let pendingVideoExportHostCaptureRequest: PendingVideoExportHostCaptureRequest | null = null

function sendExportSpeedDebug(payload: Record<string, unknown>): void {
  if (typeof fetch !== 'function') {
    return
  }
  fetch('http://127.0.0.1:7780/event', {
    method: 'POST',
    body: JSON.stringify({
      sessionId: 'manual-export-black-video',
      runId: 'pre-fix',
      ts: Date.now(),
      ...payload,
    }),
  }).catch(() => undefined)
}

function buildSampledPixelStats(pixelData: Uint8Array): Record<string, unknown> {
  const totalPixels = Math.floor(pixelData.byteLength / 4)
  if (totalPixels <= 0) {
    return {
      totalPixels: 0,
      sampledPixels: 0,
      avgRgb: 0,
      avgAlpha: 0,
      maxChannel: 0,
      nonZeroColorSamples: 0,
      nonZeroAlphaSamples: 0,
      signature: '',
    }
  }

  const sampleTarget = 64
  const stridePixels = Math.max(1, Math.floor(totalPixels / sampleTarget))
  let sampledPixels = 0
  let redSum = 0
  let greenSum = 0
  let blueSum = 0
  let alphaSum = 0
  let maxChannel = 0
  let nonZeroColorSamples = 0
  let nonZeroAlphaSamples = 0
  const signatureParts: string[] = []

  for (let pixelIndex = 0; pixelIndex < totalPixels; pixelIndex += stridePixels) {
    const offset = pixelIndex * 4
    const blue = pixelData[offset] ?? 0
    const green = pixelData[offset + 1] ?? 0
    const red = pixelData[offset + 2] ?? 0
    const alpha = pixelData[offset + 3] ?? 0
    sampledPixels += 1
    redSum += red
    greenSum += green
    blueSum += blue
    alphaSum += alpha
    if (red > 0 || green > 0 || blue > 0) {
      nonZeroColorSamples += 1
    }
    if (alpha > 0) {
      nonZeroAlphaSamples += 1
    }
    maxChannel = Math.max(maxChannel, red, green, blue, alpha)
    if (signatureParts.length < 8) {
      signatureParts.push(`${red}-${green}-${blue}-${alpha}`)
    }
  }

  const sampledColorValues = sampledPixels * 3
  return {
    totalPixels,
    sampledPixels,
    avgRgb: sampledColorValues > 0 ? Number(((redSum + greenSum + blueSum) / sampledColorValues).toFixed(2)) : 0,
    avgAlpha: sampledPixels > 0 ? Number((alphaSum / sampledPixels).toFixed(2)) : 0,
    maxChannel,
    nonZeroColorSamples,
    nonZeroAlphaSamples,
    signature: signatureParts.join('|'),
  }
}

app.commandLine.appendSwitch('autoplay-policy', 'no-user-gesture-required')
app.commandLine.appendSwitch('disable-background-timer-throttling')
app.commandLine.appendSwitch('disable-renderer-backgrounding')
app.commandLine.appendSwitch('disable-backgrounding-occluded-windows')

function escapePowerShellLiteral(value: string): string {
  return `'${String(value || '').replace(/'/g, "''")}'`
}

function normalizeDownloadUrl(value: string): string {
  const normalized = String(value || '').trim()
  if (!normalized) {
    return ''
  }
  try {
    const urlObj = new URL(normalized)
    const host = urlObj.hostname.toLowerCase()
    if (host === 'drive.google.com' || host.endsWith('.drive.google.com')) {
      const idFromQuery = urlObj.searchParams.get('id')
      if (idFromQuery) {
        return `https://drive.google.com/uc?export=download&id=${encodeURIComponent(idFromQuery)}`
      }
      const match = urlObj.pathname.match(/\/file\/d\/([^/]+)/)
      if (match?.[1]) {
        return `https://drive.google.com/uc?export=download&id=${encodeURIComponent(match[1])}`
      }
    }
  } catch {
    return normalized
  }
  return normalized
}

async function downloadToFile(targetUrl: string, targetPath: string, redirectLimit = 5): Promise<void> {
  const normalizedUrl = normalizeDownloadUrl(targetUrl)
  if (!normalizedUrl) {
    throw new Error('Missing download url.')
  }
  if (redirectLimit <= 0) {
    throw new Error('Too many redirects.')
  }

  const urlObj = new URL(normalizedUrl)
  const httpModule = urlObj.protocol === 'http:' ? http : https

  await new Promise<void>((resolve, reject) => {
    const request = httpModule.get(
      {
        protocol: urlObj.protocol,
        hostname: urlObj.hostname,
        port: urlObj.port,
        path: `${urlObj.pathname}${urlObj.search}`,
        headers: {
          'User-Agent': 'CAMXORA',
        },
      },
      (response) => {
        const statusCode = response.statusCode ?? 0
        const location = response.headers.location
        if (statusCode >= 300 && statusCode < 400 && location) {
          response.resume()
          void downloadToFile(new URL(location, urlObj).toString(), targetPath, redirectLimit - 1)
            .then(resolve)
            .catch(reject)
          return
        }

        if (statusCode < 200 || statusCode >= 300) {
          response.resume()
          reject(new Error(`Download failed with status ${statusCode}.`))
          return
        }

        const fileStream = fs.createWriteStream(targetPath)
        response.pipe(fileStream)
        fileStream.on('finish', () => {
          fileStream.close()
          resolve()
        })
        fileStream.on('error', (err) => reject(err))
      },
    )
    request.on('error', (err) => reject(err))
  })
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, Math.max(0, ms))
  })
}

async function fileExistsWithBytes(targetPath: string): Promise<boolean> {
  try {
    const stat = await fs.promises.stat(targetPath)
    return stat.isFile() && stat.size > 0
  } catch {
    return false
  }
}

async function downloadMusicTrackWithRetry(
  item: MusicTrackDownloadRequest,
  retryCount: number,
): Promise<MusicTrackDownloadResult> {
  const taskId = String(item.taskId || '').trim()
  const channel = item.channel === 'secondary' ? 'secondary' : 'primary'
  const url = String(item.url || '').trim()
  const outputDir = String(item.outputDir || '').trim()
  const targetPath = String(item.targetPath || '').trim()
  if (!taskId || !url || !outputDir || !targetPath) {
    return {
      taskId,
      channel,
      ok: false,
      outputDir: outputDir || null,
      targetPath: targetPath || null,
      skippedExisting: false,
      error: 'Missing download metadata.',
    }
  }

  const resolvedOutputDir = path.resolve(outputDir)
  const resolvedTargetPath = path.resolve(targetPath)
  const normalizedOutputDir = resolvedOutputDir.endsWith(path.sep) ? resolvedOutputDir : `${resolvedOutputDir}${path.sep}`
  if (!(resolvedTargetPath === resolvedOutputDir || resolvedTargetPath.startsWith(normalizedOutputDir))) {
    return {
      taskId,
      channel,
      ok: false,
      outputDir: resolvedOutputDir,
      targetPath: resolvedTargetPath,
      skippedExisting: false,
      error: 'Target path must stay inside the output directory.',
    }
  }

  await fs.promises.mkdir(path.dirname(resolvedTargetPath), { recursive: true })
  if (await fileExistsWithBytes(resolvedTargetPath)) {
    return {
      taskId,
      channel,
      ok: true,
      outputDir: resolvedOutputDir,
      targetPath: resolvedTargetPath,
      skippedExisting: true,
    }
  }

  const maxAttempts = Math.max(1, Math.min(5, Number(retryCount || 3)))
  let lastError = 'Unable to download track.'
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    const tempPath = `${resolvedTargetPath}.download`
    try {
      await fs.promises.rm(tempPath, { force: true })
      await downloadToFile(url, tempPath)
      const stat = await fs.promises.stat(tempPath)
      if (!stat.isFile() || stat.size <= 0) {
        throw new Error('Downloaded file is empty.')
      }
      await fs.promises.mkdir(path.dirname(resolvedTargetPath), { recursive: true })
      await fs.promises.rename(tempPath, resolvedTargetPath)
      return {
        taskId,
        channel,
        ok: true,
        outputDir: resolvedOutputDir,
        targetPath: resolvedTargetPath,
        skippedExisting: false,
      }
    } catch (error) {
      lastError = error instanceof Error ? error.message : 'Unable to download track.'
      try {
        await fs.promises.rm(tempPath, { force: true })
      } catch {
        // ignore cleanup failures
      }
      if (/status 404/i.test(lastError) || attempt >= maxAttempts) {
        break
      }
      await sleep(800 * attempt)
    }
  }

  return {
    taskId,
    channel,
    ok: false,
    outputDir: resolvedOutputDir,
    targetPath: resolvedTargetPath,
    skippedExisting: false,
    error: lastError,
  }
}

async function runPowerShell(command: string): Promise<void> {
  await new Promise<void>((resolve, reject) => {
    const child = spawn(
      'powershell.exe',
      ['-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-Command', command],
      { windowsHide: true },
    )
    let stderr = ''
    child.stderr.on('data', (chunk) => {
      stderr += String(chunk || '')
    })
    child.on('error', (err) => reject(err))
    child.on('close', (code) => {
      if (code === 0) {
        resolve()
        return
      }
      reject(new Error((stderr || '').trim() || `PowerShell exited with code ${code}`))
    })
  })
}

async function expandArchive(zipPath: string, destinationDir: string): Promise<void> {
  const command = `Expand-Archive -LiteralPath ${escapePowerShellLiteral(zipPath)} -DestinationPath ${escapePowerShellLiteral(destinationDir)} -Force`
  await runPowerShell(command)
}

async function listFilesRecursive(baseDir: string): Promise<string[]> {
  const results: string[] = []
  const stack: string[] = [baseDir]
  while (stack.length) {
    const current = stack.pop()
    if (!current) continue
    const entries = await fs.promises.readdir(current, { withFileTypes: true })
    for (const entry of entries) {
      const nextPath = path.join(current, entry.name)
      if (entry.isDirectory()) {
        stack.push(nextPath)
        continue
      }
      if (entry.isFile()) {
        results.push(nextPath)
      }
    }
  }
  return results
}

let splashWindow: BrowserWindow | null = null
let mainWindow: BrowserWindow | null = null
let videoExportHostWindow: BrowserWindow | null = null
let shouldShowMainWindow = false
let splashFallbackTimer: NodeJS.Timeout | null = null
let splashCreatedAt: number | null = null
const mainWindowDefaultSize = { width: 1920, height: 1080 }
const minSplashVisibleMs = 900

if (process.platform === 'win32') {
  app.setAppUserModelId('com.camxora.desktop')
}

function withHashRoute(baseUrl: string, route: string): string {
  const normalizedRoute = route.startsWith('/') ? route : `/${route}`
  return `${baseUrl}#${normalizedRoute}`
}

function showMainWindowIfReady(): void {
  if (!mainWindow || mainWindow.isDestroyed()) {
    return
  }

  mainWindow.show()
  mainWindow.focus()
}

function isManualVideoExportSessionActive(): boolean {
  return activeVideoExport.branch === null && (activeVideoExport.running || activeVideoExportHost.pendingScene != null)
}

function rejectPendingVideoExportHostCapture(errorMessage: string): void {
  if (!pendingVideoExportHostCaptureRequest) {
    return
  }
  const pendingRequest = pendingVideoExportHostCaptureRequest
  pendingVideoExportHostCaptureRequest = null
  clearTimeout(pendingRequest.timeoutId)
  pendingRequest.reject(new Error(errorMessage))
}

function resetVideoExportHostSessionState(): void {
  rejectPendingVideoExportHostCapture('Manual WebGPU export capture request was reset before the GPU frame arrived.')
  activeVideoExportHost.ready = false
  activeVideoExportHost.pendingScene = null
  activeVideoExportHost.currentStatus = null
  activeVideoExportHost.currentPlayback = null
  activeVideoExportHost.currentScene = null
  activeVideoExportHost.captureProbeRunning = false
}

function clearManualVideoExportBootstrap(
  message: string,
  options?: {
    lastOutputPath?: string | null
    outputDir?: string | null
    completedJobs?: number
    totalJobs?: number
  },
): void {
  activeVideoExport.running = false
  activeVideoExport.branch = null
  activeVideoExport.runDir = null
  activeVideoExport.outputDir = options?.outputDir ?? null
  activeVideoExport.currentOutputPath = null
  activeVideoExport.workers = 1
  activeVideoExport.autoMerge = false
  activeVideoExport.mergeRunning = false
  activeVideoExport.currentStatus = message
  activeVideoExport.totalJobs = options?.totalJobs ?? 0
  activeVideoExport.completedJobs = options?.completedJobs ?? 0
  activeVideoExport.lastOutputPath = options?.lastOutputPath ?? null
  activeVideoExport.lastMergedOutputPath = null
  activeVideoExport.startedAtMs = null
  activeVideoExport.lastProgressEventAtMs = 0
  activeVideoExport.selectedMp3Path = ''
  activeVideoExport.mp3List = []
  activeVideoExport.queue = []
  activeVideoExport.stopRequested = false
}

function computeVideoExportProgressPercent(completedJobs: number, totalJobs: number): number {
  if (!Number.isFinite(totalJobs) || totalJobs <= 0) {
    return 0
  }
  return Math.max(0, Math.min(100, (Math.max(0, completedJobs) / totalJobs) * 100))
}

function computeVideoExportEstimatedRemainingSec(
  startedAtMs: number | null,
  completedJobs: number,
  totalJobs: number,
): number | null {
  if (!startedAtMs || !Number.isFinite(startedAtMs) || !Number.isFinite(totalJobs) || totalJobs <= 0) {
    return null
  }
  if (!Number.isFinite(completedJobs) || completedJobs <= 0 || completedJobs >= totalJobs) {
    return completedJobs >= totalJobs ? 0 : null
  }
  const elapsedMs = Math.max(1, Date.now() - startedAtMs)
  const avgMsPerJob = elapsedMs / completedJobs
  const remainingJobs = Math.max(0, totalJobs - completedJobs)
  return Math.max(0, Math.ceil((avgMsPerJob * remainingJobs) / 1000))
}

function emitVideoExportProgressUpdate(force = false): void {
  const now = Date.now()
  if (!force && now - activeVideoExport.lastProgressEventAtMs < 250) {
    return
  }
  activeVideoExport.lastProgressEventAtMs = now
  emitVideoWorkspaceEvent('export', 0)
}

function isVideoExportHostWindowAvailable(): boolean {
  return Boolean(videoExportHostWindow && !videoExportHostWindow.isDestroyed())
}

function isVideoExportHostSender(sender: Electron.WebContents): boolean {
  return Boolean(
    videoExportHostWindow &&
      !videoExportHostWindow.isDestroyed() &&
      sender.id === videoExportHostWindow.webContents.id,
  )
}

function sendSceneToVideoExportHost(scene: ManualVideoExportRequest['scene']): boolean {
  if (!isVideoExportHostWindowAvailable() || !activeVideoExportHost.ready || !videoExportHostWindow) {
    return false
  }
  const width = Math.max(1, Math.round(Number(scene.output.width) || 1))
  const height = Math.max(1, Math.round(Number(scene.output.height) || 1))
  videoExportHostWindow.setContentSize(width, height, false)
  videoExportHostWindow.webContents.send('video-export-host:scene', scene)
  return true
}

function sendCommandToVideoExportHost(command: VideoExportHostCommandPayload): boolean {
  if (!isVideoExportHostWindowAvailable() || !activeVideoExportHost.ready || !videoExportHostWindow) {
    return false
  }
  videoExportHostWindow.webContents.send('video-export-host:command', command)
  return true
}

function flushPendingVideoExportHostScene(): boolean {
  const pendingScene = activeVideoExportHost.pendingScene
  if (!pendingScene) {
    return false
  }
  const dispatched = sendSceneToVideoExportHost(pendingScene)
  if (dispatched) {
    activeVideoExportHost.pendingScene = null
  }
  return dispatched
}

function handleVideoExportHostClosed(): void {
  videoExportHostWindow = null
  const shouldReportClosure = isManualVideoExportSessionActive()
  resetVideoExportHostSessionState()
  if (!shouldReportClosure) {
    return
  }
  clearManualVideoExportBootstrap('Manual WebGPU export host closed before frame capture started.')
  emitVideoWorkspaceEvent('export', 20)
}

function closeVideoExportHostWindowSilently(): void {
  if (!videoExportHostWindow || videoExportHostWindow.isDestroyed()) {
    videoExportHostWindow = null
    return
  }
  const hostWindow = videoExportHostWindow
  videoExportHostWindow = null
  try {
    hostWindow.close()
  } catch {
    // ignore close failures
  }
}

function resolveManualVideoExportOutputDir(scene: ManualVideoExportRequest['scene']): string {
  const settings = parseDefaultSettings()
  const configuredOutputDir = String(settings?.videoRenderOutputDir ?? '').trim()
  if (configuredOutputDir) {
    return configuredOutputDir
  }

  const audioPath = String(scene.assets.audioPath || '').trim()
  if (audioPath) {
    return path.dirname(audioPath)
  }

  return app.getPath('videos')
}

async function waitForVideoExportHostPlayback(options: {
  predicate: (playback: VideoExportHostPlaybackPayload | null) => boolean
  timeoutMs: number
  pollMs?: number
}): Promise<VideoExportHostPlaybackPayload> {
  const startedAt = Date.now()
  const pollMs = Math.max(16, options.pollMs ?? 50)

  while (Date.now() - startedAt <= options.timeoutMs) {
    if (!isManualVideoExportSessionActive() || activeVideoExport.stopRequested) {
      throw new Error('Manual WebGPU export was stopped before the host synchronized.')
    }
    const playback = activeVideoExportHost.currentPlayback
    if (options.predicate(playback)) {
      return playback as VideoExportHostPlaybackPayload
    }
    await sleep(pollMs)
  }

  throw new Error('Manual WebGPU export host did not reach the requested playback state in time.')
}

function requestVideoExportHostCaptureFrame(
  timeoutMs: number,
  timeSec: number,
): Promise<VideoExportHostCaptureFramePayload> {
  if (pendingVideoExportHostCaptureRequest) {
    return Promise.reject(
      new Error('Manual WebGPU export tried to start a new GPU capture before the previous one completed.'),
    )
  }
  if (!isVideoExportHostWindowAvailable() || !activeVideoExportHost.ready) {
    return Promise.reject(new Error('Manual WebGPU export host is not ready for GPU readback capture.'))
  }
  const requestId = crypto.randomUUID()
  const requestStartedAt = Date.now()
  return new Promise<VideoExportHostCaptureFramePayload>((resolve, reject) => {
    const timeoutId = setTimeout(() => {
      if (pendingVideoExportHostCaptureRequest?.requestId !== requestId) {
        return
      }
      pendingVideoExportHostCaptureRequest = null
      reject(new Error('Manual WebGPU export host did not return a GPU frame in time.'))
    }, Math.max(500, timeoutMs))
    pendingVideoExportHostCaptureRequest = {
      requestId,
      resolve: (payload) => {
        // #region debug-point C:capture-response
        sendExportSpeedDebug({
          hypothesisId: 'C',
          location: 'main:index.ts:requestVideoExportHostCaptureFrame:resolve',
          msg: '[DEBUG] export capture response received in main',
          data: {
            requestId,
            elapsedMs: Date.now() - requestStartedAt,
            width: payload.width,
            height: payload.height,
            bytes: payload.pixelData.byteLength,
          },
        })
        // #endregion
        resolve(payload)
      },
      reject,
      timeoutId,
    }
    // #region debug-point C:capture-dispatch
    sendExportSpeedDebug({
      hypothesisId: 'C',
      location: 'main:index.ts:requestVideoExportHostCaptureFrame:dispatch',
      msg: '[DEBUG] export capture request dispatched from main',
      data: {
        requestId,
        timeoutMs,
      },
    })
    // #endregion
    const dispatched = sendCommandToVideoExportHost({
      type: 'capture-frame',
      requestId,
      timeSec,
    })
    if (!dispatched) {
      clearTimeout(timeoutId)
      pendingVideoExportHostCaptureRequest = null
      reject(new Error('Manual WebGPU export could not dispatch the GPU frame capture command.'))
    }
  })
}

function buildManualVideoExportVideoPath(
  scene: ManualVideoExportRequest['scene'],
  outputDir: string,
): string {
  const audioPath = String(scene.assets.audioPath || '').trim()
  const stem = audioPath ? path.parse(audioPath).name : 'manual-export'
  const now = new Date()
  const stamp = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}-${String(now.getHours()).padStart(2, '0')}${String(now.getMinutes()).padStart(2, '0')}${String(now.getSeconds()).padStart(2, '0')}`
  return path.join(outputDir, `${stem}_WEBGPU_${stamp}.mp4`)
}

async function resolveManualVideoExportDurationSec(
  scene: ManualVideoExportRequest['scene'],
  ffmpegPath: string,
): Promise<number> {
  const playbackDurationSec = Number(activeVideoExportHost.currentPlayback?.durationSec ?? 0)
  if (Number.isFinite(playbackDurationSec) && playbackDurationSec > 0.05) {
    return playbackDurationSec
  }

  const audioPath = String(scene.assets.audioPath || '').trim()
  const ffprobePath = resolveFfprobePath(ffmpegPath)
  if (audioPath && ffprobePath) {
    const probedDurationSec = await probeVideoDuration(audioPath, ffprobePath)
    if (Number.isFinite(probedDurationSec) && probedDurationSec > 0.05) {
      return probedDurationSec
    }
  }

  return 0
}

function writeBufferToChildStdin(
  child: ReturnType<typeof spawn>,
  buffer: Uint8Array,
  errorMessage: string,
): Promise<void> {
  return new Promise<void>((resolve, reject) => {
    const stdin = child.stdin
    if (!stdin || stdin.destroyed || !stdin.writable) {
      reject(new Error(errorMessage))
      return
    }
    stdin.write(buffer, (error) => {
      if (error) {
        reject(error)
        return
      }
      resolve()
    })
  })
}

function endChildStdin(child: ReturnType<typeof spawn>): Promise<void> {
  return new Promise<void>((resolve, reject) => {
    const stdin = child.stdin
    if (!stdin || stdin.destroyed) {
      resolve()
      return
    }
    const handleError = (error: Error) => {
      stdin.off('finish', handleFinish)
      reject(error)
    }
    const handleFinish = () => {
      stdin.off('error', handleError)
      resolve()
    }
    stdin.once('error', handleError)
    stdin.once('finish', handleFinish)
    stdin.end()
  })
}

async function streamManualVideoExportFrames(options: {
  ffmpegPath: string
  fps: number
  audioPath: string
  outputPath: string
  width: number
  height: number
  runCapture: (writeFrame: (frameBuffer: Uint8Array, frameIndex: number, totalFrames: number) => Promise<void>) => Promise<void>
  onStartEncoding: (message: string) => void
  onFinishEncoding: (message: string) => void
}): Promise<void> {
  await new Promise<void>(async (resolve, reject) => {
    let stderr = ''
    const jobKey = `__manual-encode__${options.outputPath}`
    const child = spawn(
      options.ffmpegPath,
      [
        '-y',
        '-f',
        'rawvideo',
        '-pix_fmt',
        'bgra',
        '-video_size',
        `${options.width}x${options.height}`,
        '-framerate',
        String(options.fps),
        '-i',
        '-',
        '-i',
        options.audioPath,
        '-c:v',
        'libx264',
        '-pix_fmt',
        'yuv420p',
        '-preset',
        'medium',
        '-r',
        String(options.fps),
        '-c:a',
        'aac',
        '-shortest',
        '-movflags',
        '+faststart',
        options.outputPath,
      ],
      {
        cwd: getProjectRootPath(),
        windowsHide: true,
        stdio: ['pipe', 'ignore', 'pipe'],
      },
    )

    activeVideoExport.activeJobs.set(jobKey, child)

    child.stderr?.on('data', (chunk) => {
      stderr += String(chunk || '')
    })
    child.on('error', (error) => {
      activeVideoExport.activeJobs.delete(jobKey)
      reject(error)
    })
    child.on('close', (code) => {
      activeVideoExport.activeJobs.delete(jobKey)
      if (code === 0) {
        resolve()
        return
      }
      reject(new Error((stderr || '').trim() || `Manual WebGPU encode exited with code ${code}`))
    })

    try {
      options.onStartEncoding('Streaming WebGPU frames directly into ffmpeg…')
      await options.runCapture((frameBuffer, frameIndex, totalFrames) => {
        if (frameIndex + 1 === totalFrames) {
          options.onFinishEncoding('Finalizing MP4 stream…')
        }
        return writeBufferToChildStdin(
          child,
          frameBuffer,
          'Manual WebGPU export encoder is no longer accepting frames.',
        )
      })
      await endChildStdin(child)
    } catch (error) {
      try {
        child.kill()
      } catch {
        // ignore kill failures
      }
      reject(error instanceof Error ? error : new Error('Manual WebGPU frame streaming failed.'))
    }
  })
}

async function runManualVideoExportCapture(): Promise<void> {
  const scene = activeVideoExportHost.currentScene
  if (!scene || !videoExportHostWindow || videoExportHostWindow.isDestroyed()) {
    throw new Error('Manual WebGPU export host is not ready for frame capture.')
  }

  const outputDir = resolveManualVideoExportOutputDir(scene)
  const settings = parseDefaultSettings()
  const ffmpegPath = getStringSetting(settings, 'ffmpegPath', 'ffmpeg')
  const audioPath = String(scene.assets.audioPath || '').trim()
  const fps = Math.max(1, Math.round(Number(scene.output.fps) || 60))
  const width = Math.max(1, Math.round(Number(scene.output.width) || 1920))
  const height = Math.max(1, Math.round(Number(scene.output.height) || 1080))
  activeVideoExport.outputDir = outputDir
  activeVideoExport.currentStatus = 'Synchronizing manual WebGPU export host to the timeline start…'
  emitVideoWorkspaceEvent('export', 20)
  sendCommandToVideoExportHost({ type: 'stop' })

  await waitForVideoExportHostPlayback({
    predicate: (playback) =>
      Boolean(playback?.isReady) &&
      !Boolean(playback?.isLoading),
    timeoutMs: 15_000,
  })

  const durationSec = await resolveManualVideoExportDurationSec(scene, ffmpegPath)
  if (!Number.isFinite(durationSec) || durationSec <= 0.05) {
    throw new Error('Manual WebGPU export could not determine the selected audio duration.')
  }

  const totalFrames = Math.max(1, Math.ceil(durationSec * fps))
  const lastFrameTimeSec = Math.max(0, durationSec - 1 / fps)
  const outputPath = buildManualVideoExportVideoPath(scene, outputDir)
  await fs.promises.mkdir(outputDir, { recursive: true })

  activeVideoExport.currentOutputPath = outputPath
  activeVideoExport.totalJobs = totalFrames
  activeVideoExport.completedJobs = 0
  activeVideoExport.startedAtMs = Date.now()
  activeVideoExport.lastProgressEventAtMs = 0
  emitVideoExportProgressUpdate(true)

  await streamManualVideoExportFrames({
    ffmpegPath,
    fps,
    audioPath,
    outputPath,
    width,
    height,
    onStartEncoding: (message) => {
      activeVideoExport.currentStatus = message
      emitVideoExportProgressUpdate(true)
    },
    onFinishEncoding: (message) => {
      activeVideoExport.currentStatus = message
      emitVideoExportProgressUpdate(true)
    },
    runCapture: async (writeFrame) => {
      for (let frameIndex = 0; frameIndex < totalFrames; frameIndex += 1) {
        if (activeVideoExport.stopRequested || !isManualVideoExportSessionActive()) {
          throw new Error('Manual WebGPU export was stopped.')
        }
        if (!videoExportHostWindow || videoExportHostWindow.isDestroyed()) {
          throw new Error('Manual WebGPU export host became unavailable before capture.')
        }

        const targetTimeSec = Math.min(frameIndex / fps, lastFrameTimeSec)
        const sampleFrame = frameIndex < 3 || frameIndex % 300 === 0
        if (sampleFrame) {
          // #region debug-point B:seek-sync
          sendExportSpeedDebug({
            hypothesisId: 'B',
            location: 'main:index.ts:runManualVideoExportCapture:seek',
            msg: '[DEBUG] export frame seek synchronized',
            data: {
              frameIndex,
              totalFrames,
              targetTimeSec: Number(targetTimeSec.toFixed(4)),
              elapsedMs: 0,
            },
          })
          // #endregion
        }

        const captureStartedAt = sampleFrame ? Date.now() : 0
        const capture = await requestVideoExportHostCaptureFrame(8_000, targetTimeSec)
        const frameBuffer = capture.pixelData
        const expectedByteLength = width * height * 4
        if (frameBuffer.byteLength < expectedByteLength) {
          throw new Error('Manual WebGPU export captured an incomplete frame buffer.')
        }
        if (sampleFrame) {
          // #region debug-point K:frame-buffer-stats
          sendExportSpeedDebug({
            hypothesisId: 'K',
            location: 'main:index.ts:runManualVideoExportCapture:buffer-stats',
            msg: '[DEBUG] sampled frame buffer stats before ffmpeg write',
            data: {
              frameIndex,
              totalFrames,
              targetTimeSec: Number(targetTimeSec.toFixed(4)),
              ...buildSampledPixelStats(frameBuffer.subarray(0, expectedByteLength)),
            },
          })
          // #endregion
        }

        const writeStartedAt = sampleFrame ? Date.now() : 0
        await writeFrame(frameBuffer.subarray(0, expectedByteLength), frameIndex, totalFrames)
        if (sampleFrame) {
          // #region debug-point E:frame-pipeline
          sendExportSpeedDebug({
            hypothesisId: 'E',
            location: 'main:index.ts:runManualVideoExportCapture:frame',
            msg: '[DEBUG] export frame pipeline timing in main',
            data: {
              frameIndex,
              totalFrames,
              captureElapsedMs: Date.now() - captureStartedAt,
              ffmpegWriteElapsedMs: Date.now() - writeStartedAt,
              bytes: expectedByteLength,
            },
          })
          // #endregion
        }

        activeVideoExport.completedJobs = frameIndex + 1
        activeVideoExport.currentStatus = `Streaming manual WebGPU frames ${frameIndex + 1}/${totalFrames}…`
        emitVideoExportProgressUpdate()
      }
    },
  })

  closeVideoExportHostWindowSilently()
  resetVideoExportHostSessionState()

  if (!isValidExportOutput(outputPath)) {
    throw new Error('Manual WebGPU export did not produce a valid MP4 output.')
  }

  clearManualVideoExportBootstrap('Manual WebGPU export complete.', {
    lastOutputPath: outputPath,
    outputDir,
    completedJobs: 1,
    totalJobs: 1,
  })
  emitVideoWorkspaceEvent('export', 20)
}

function clearSplashFallbackTimer(): void {
  if (splashFallbackTimer) {
    clearTimeout(splashFallbackTimer)
    splashFallbackTimer = null
  }
}

async function createVideoExportHostWindow(): Promise<BrowserWindow> {
  if (videoExportHostWindow && !videoExportHostWindow.isDestroyed()) {
    return videoExportHostWindow
  }

  const hostWindow = new BrowserWindow({
    width: 1280,
    height: 720,
    useContentSize: true,
    show: false,
    frame: false,
    resizable: false,
    minimizable: false,
    maximizable: false,
    fullscreenable: false,
    skipTaskbar: true,
    backgroundColor: '#000000',
    icon: appIconPath,
    webPreferences: {
      preload: path.join(__dirname, '../preload/index.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
      backgroundThrottling: false,
    },
  })

  hostWindow.on('closed', () => {
    if (videoExportHostWindow === hostWindow) {
      handleVideoExportHostClosed()
    }
  })

  hostWindow.webContents.on('render-process-gone', (_event, details) => {
    if (videoExportHostWindow !== hostWindow) {
      return
    }
    clearManualVideoExportBootstrap(
      `Manual WebGPU export host exited unexpectedly${details.reason ? ` (${details.reason})` : ''}.`,
    )
    emitVideoWorkspaceEvent('export', 20)
  })

  hostWindow.webContents.on('did-fail-load', (_event, errorCode, errorDescription) => {
    if (videoExportHostWindow !== hostWindow) {
      return
    }
    clearManualVideoExportBootstrap(
      `Manual WebGPU export host failed to load (${errorCode}): ${errorDescription || 'Unknown error.'}`,
    )
    emitVideoWorkspaceEvent('export', 20)
  })

  videoExportHostWindow = hostWindow
  activeVideoExportHost.ready = false

  const hostUrl = withHashRoute(getRendererUrl(), '/export-host')
  await hostWindow.loadURL(hostUrl)
  return hostWindow
}

async function ensureVideoExportHostWindow(): Promise<BrowserWindow> {
  return createVideoExportHostWindow()
}

function closeSplashAndShowMain(): void {
  shouldShowMainWindow = true
  clearSplashFallbackTimer()

  if (!splashWindow || splashWindow.isDestroyed()) {
    splashWindow = null
    showMainWindowIfReady()
    return
  }

  const elapsed = splashCreatedAt ? Date.now() - splashCreatedAt : minSplashVisibleMs
  const remaining = Math.max(0, minSplashVisibleMs - elapsed)

  setTimeout(() => {
    if (splashWindow && !splashWindow.isDestroyed()) {
      splashWindow.close()
    }
    splashWindow = null
    showMainWindowIfReady()
  }, remaining)
}

function restoreMainWindowToDefaultSize(): void {
  if (!mainWindow || mainWindow.isDestroyed()) {
    return
  }

  const activeDisplay = screen.getDisplayNearestPoint(screen.getCursorScreenPoint())
  const workArea = activeDisplay.workArea

  const width = Math.min(mainWindowDefaultSize.width, workArea.width)
  const height = Math.min(mainWindowDefaultSize.height, workArea.height)
  const x = workArea.x + Math.round((workArea.width - width) / 2)
  const y = workArea.y + Math.round((workArea.height - height) / 2)

  mainWindow.setBounds({ x, y, width, height }, false)
}

function readSecureStore(): SecureRecord {
  if (!fs.existsSync(secureStorePath)) {
    return {}
  }

  try {
    const raw = fs.readFileSync(secureStorePath, 'utf8')
    return JSON.parse(raw) as SecureRecord
  } catch {
    return {}
  }
}

function writeSecureStore(store: SecureRecord): void {
  fs.mkdirSync(path.dirname(secureStorePath), { recursive: true })
  fs.writeFileSync(secureStorePath, JSON.stringify(store, null, 2), 'utf8')
}

function encodeValue(value: string): string {
  if (!safeStorage.isEncryptionAvailable()) {
    return value
  }

  return safeStorage.encryptString(value).toString('base64')
}

function decodeValue(value: string): string | null {
  if (!safeStorage.isEncryptionAvailable()) {
    return value
  }

  try {
    return safeStorage.decryptString(Buffer.from(value, 'base64'))
  } catch {
    return null
  }
}

function readVideoWorkspacePrefs(): VideoWorkspacePrefs {
  try {
    if (!fs.existsSync(videoWorkspacePrefsPath)) {
      return {}
    }
    return JSON.parse(fs.readFileSync(videoWorkspacePrefsPath, 'utf8')) as VideoWorkspacePrefs
  } catch {
    return {}
  }
}

function writeVideoWorkspacePrefs(prefs: VideoWorkspacePrefs): void {
  fs.mkdirSync(path.dirname(videoWorkspacePrefsPath), { recursive: true })
  fs.writeFileSync(videoWorkspacePrefsPath, JSON.stringify(prefs, null, 2), 'utf8')
}

function getProjectRootPath(): string {
  return path.resolve(app.getAppPath(), '..')
}

function getPythonAppPath(): string {
  return path.join(getProjectRootPath(), 'python_app')
}

function getVideoTemplatesPath(): string {
  return path.join(getPythonAppPath(), 'video_templates_local.json')
}

function getMusicModelPath(): string {
  return path.join(getPythonAppPath(), 'models', 'music_model.py')
}

function readJsonFile<T>(filePath: string): T | null {
  try {
    if (!fs.existsSync(filePath)) {
      return null
    }
    return JSON.parse(fs.readFileSync(filePath, 'utf8')) as T
  } catch {
    return null
  }
}

function writeJsonFile(filePath: string, value: unknown): void {
  fs.mkdirSync(path.dirname(filePath), { recursive: true })
  fs.writeFileSync(filePath, JSON.stringify(value, null, 2), 'utf8')
}

async function resolveVideoAudioAnalysisCachePath(sourcePath: string): Promise<string | null> {
  const normalizedSourcePath = String(sourcePath || '').trim()
  if (!normalizedSourcePath) {
    return null
  }
  try {
    const resolvedSourcePath = path.resolve(normalizedSourcePath)
    const stat = await fs.promises.stat(resolvedSourcePath)
    if (!stat.isFile()) {
      return null
    }
    const cacheKey = crypto
      .createHash('sha1')
      .update(`${resolvedSourcePath}|${stat.size}|${stat.mtimeMs}`)
      .digest('hex')
    return path.join(videoAudioAnalysisCacheRoot, `${cacheKey}.json`)
  } catch {
    return null
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function mergeUnknown(base: unknown, patch: unknown): unknown {
  if (Array.isArray(patch)) {
    return patch
  }

  if (isRecord(base) && isRecord(patch)) {
    const next: Record<string, unknown> = { ...base }
    Object.entries(patch).forEach(([key, value]) => {
      next[key] = mergeUnknown(next[key], value)
    })
    return next
  }

  if (isRecord(patch)) {
    const next: Record<string, unknown> = {}
    Object.entries(patch).forEach(([key, value]) => {
      next[key] = mergeUnknown(undefined, value)
    })
    return next
  }

  return patch
}

function parseDefaultSettings(): Record<string, unknown> | null {
  try {
    const filePath = getMusicModelPath()
    if (!fs.existsSync(filePath)) {
      return null
    }

    const raw = fs.readFileSync(filePath, 'utf8')
    const match = raw.match(/DEFAULT_SETTINGS:\s*dict\s*=\s*(\{[\s\S]*?\n\})/)
    if (!match) {
      return null
    }

    const pythonDict = match[1]
      .replace(/\bTrue\b/g, 'true')
      .replace(/\bFalse\b/g, 'false')
      .replace(/\bNone\b/g, 'null')

    return Function(`"use strict"; return (${pythonDict});`)() as Record<string, unknown>
  } catch {
    return null
  }
}

function parseResolution(resolution: string): { width: number; height: number } {
  const match = /^(\d+)\s*x\s*(\d+)$/i.exec(String(resolution || '').trim())
  const width = match ? Number(match[1]) : 1920
  const height = match ? Number(match[2]) : 1080
  return {
    width: width > 0 ? width : 1920,
    height: height > 0 ? height : 1080,
  }
}

function getStringSetting(settings: Record<string, unknown> | null, key: string, fallback = ''): string {
  const value = settings?.[key]
  return typeof value === 'string' ? value.trim() || fallback : fallback
}

function getNumberSetting(settings: Record<string, unknown> | null, key: string, fallback: number): number {
  const value = settings?.[key]
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value
  }
  if (typeof value === 'string') {
    const parsed = Number(value)
    if (Number.isFinite(parsed)) {
      return parsed
    }
  }
  return fallback
}

function listMp3Files(runDir: string): Array<{ name: string; path: string }> {
  const normalized = String(runDir || '').trim()
  if (!normalized || !fs.existsSync(normalized)) {
    return []
  }
  return fs
    .readdirSync(normalized, { withFileTypes: true })
    .filter((entry) => entry.isFile() && entry.name.toLowerCase().endsWith('.mp3'))
    .map((entry) => ({
      name: entry.name,
      path: path.join(normalized, entry.name),
    }))
    .sort((left, right) => left.name.localeCompare(right.name))
}

function resolveWorkspaceMp3Selection(
  preferredPath: string,
): { selectedMp3Path: string; mp3Directory: string; mp3List: Array<{ name: string; path: string }> } {
  const normalizedPath = String(preferredPath || '').trim()
  if (!normalizedPath || !fs.existsSync(normalizedPath)) {
    return {
      selectedMp3Path: '',
      mp3Directory: '',
      mp3List: [],
    }
  }

  const stat = fs.statSync(normalizedPath)
  const directoryPath = stat.isDirectory() ? normalizedPath : path.dirname(normalizedPath)
  const mp3List = stat.isDirectory()
    ? listMp3Files(directoryPath)
    : (() => {
        const listed = listMp3Files(directoryPath)
        if (listed.some((item) => item.path === normalizedPath)) {
          return listed
        }
        return [
          ...listed,
          {
            name: path.basename(normalizedPath),
            path: normalizedPath,
          },
        ].sort((left, right) => left.name.localeCompare(right.name))
      })()
  const selectedMp3Path = mp3List.find((item) => item.path === normalizedPath)?.path ?? mp3List[0]?.path ?? ''

  return {
    selectedMp3Path,
    mp3Directory: directoryPath,
    mp3List,
  }
}

function isValidExportOutput(targetPath: string): boolean {
  try {
    return fs.existsSync(targetPath) && fs.statSync(targetPath).isFile() && fs.statSync(targetPath).size > 50_000
  } catch {
    return false
  }
}

function resolvePythonCommand(settings: Record<string, unknown> | null): { command: string; argsPrefix: string[] } {
  const configured = getStringSetting(settings, 'pythonPath')
  if (configured) {
    return { command: configured, argsPrefix: [] }
  }
  const localVenv = path.join(getProjectRootPath(), '.venv', 'Scripts', 'python.exe')
  if (fs.existsSync(localVenv)) {
    return { command: localVenv, argsPrefix: [] }
  }
  return { command: 'python', argsPrefix: [] }
}

function resetActiveVideoExportState(message: string): void {
  activeVideoExport.running = false
  activeVideoExport.mergeRunning = false
  activeVideoExport.currentStatus = message
  activeVideoExport.currentOutputPath = null
  activeVideoExport.startedAtMs = null
  activeVideoExport.lastProgressEventAtMs = 0
  activeVideoExport.selectedMp3Path = ''
  activeVideoExport.mp3List = []
  activeVideoExport.queue = []
  activeVideoExport.activeJobs.clear()
  activeVideoExport.stopRequested = false
  emitVideoWorkspaceEvent('export', 60)
}

function safeBatchSuffix(batchId: string): string {
  const text = String(batchId || '').trim()
  const match = /^batch-(\d{4}-\d{2}-\d{2})-(\d+)-(\d+)$/i.exec(text)
  if (match) {
    return `${match[1]}_${match[2]}_${match[3]}`
  }
  const safe = text.replace(/[^a-zA-Z0-9_.-]+/g, '_')
  return safe.length > 80 ? safe.slice(-80) : safe
}

function normalizeMergeRole(role: string): 'PRIMARY' | 'SECONDARY' {
  const normalized = String(role || '').trim().toLowerCase()
  return normalized === 'alt' || normalized === 'secondary' ? 'SECONDARY' : 'PRIMARY'
}

function isAutoMergeEnabledForBranch(
  settings: Record<string, unknown> | null,
  branch: VideoExportBranch,
): boolean {
  const autoMergeAfterVideo = Boolean(settings?.autoMergeAfterVideo ?? false)
  if (!autoMergeAfterVideo) {
    return false
  }
  if (branch === 'reel') {
    return Boolean(settings?.autoReelAfterVideo ?? false)
  }
  return true
}

function resolvePipelineExportSettings(
  request: VideoPipelineExportRequest,
): Record<string, unknown> {
  const defaults = parseDefaultSettings() ?? {}
  const live = isRecord(request.settings) ? request.settings : null
  if (!live) {
    return defaults
  }
  return { ...defaults, ...live }
}

function resolvePipelineAutoMerge(
  request: VideoPipelineExportRequest,
  settings: Record<string, unknown>,
  branch: VideoExportBranch,
): boolean {
  if (typeof request.autoMerge === 'boolean') {
    if (!request.autoMerge) {
      return false
    }
    if (branch === 'reel') {
      return Boolean(settings.autoReelAfterVideo ?? false)
    }
    return true
  }
  return isAutoMergeEnabledForBranch(settings, branch)
}

function buildMergedOutputPath(outputDir: string, batchId: string, role: string, branch: VideoExportBranch): string {
  const suffix = safeBatchSuffix(batchId) || 'batch'
  const normalizedRole = normalizeMergeRole(role)
  const fileName =
    branch === 'reel'
      ? `MERGED_REEL_${normalizedRole}_${suffix}.mp4`
      : `MERGED_${normalizedRole}_${suffix}.mp4`
  return path.join(outputDir, fileName)
}

function listBranchExportOutputs(outputDir: string, branch: VideoExportBranch): string[] {
  try {
    const entries = fs.readdirSync(outputDir, { withFileTypes: true })
    return entries
      .filter((entry) => entry.isFile())
      .map((entry) => entry.name)
      .filter((name) => {
        const lower = name.toLowerCase()
        if (!lower.endsWith('.mp4')) {
          return false
        }
        if (lower.startsWith('merged_')) {
          return false
        }
        return branch === 'reel' ? lower.endsWith('_reel.mp4') : !lower.endsWith('_reel.mp4')
      })
      .map((name) => path.join(outputDir, name))
      .filter((targetPath) => isValidExportOutput(targetPath))
      .sort((left, right) => left.localeCompare(right))
  } catch {
    return []
  }
}

function escapeFfconcatPath(targetPath: string): string {
  return String(targetPath || '').replace(/'/g, "'\\''")
}

async function isFileStable(targetPath: string): Promise<boolean> {
  let previousStat: fs.Stats
  try {
    previousStat = await fs.promises.stat(targetPath)
    if (!previousStat.isFile()) {
      return false
    }
    const handle = await fs.promises.open(targetPath, 'r')
    await handle.read(Buffer.alloc(1), 0, 1, 0)
    await handle.close()
  } catch {
    return false
  }

  for (let attempt = 0; attempt < 10; attempt += 1) {
    await sleep(400)
    try {
      const currentStat = await fs.promises.stat(targetPath)
      if (
        previousStat.size === currentStat.size &&
        previousStat.mtimeMs === currentStat.mtimeMs
      ) {
        return true
      }
      previousStat = currentStat
    } catch {
      return false
    }
  }
  return false
}

function resolveFfprobePath(ffmpegPath: string): string {
  try {
    const ffmpegDir = ffmpegPath ? path.dirname(ffmpegPath) : ''
    const sibling = ffmpegDir ? path.join(ffmpegDir, 'ffprobe.exe') : 'ffprobe.exe'
    if (fs.existsSync(sibling)) {
      return sibling
    }
    const renamed = ffmpegPath ? path.join(path.dirname(ffmpegPath), 'ffprobe.exe') : ''
    if (renamed && fs.existsSync(renamed)) {
      return renamed
    }
  } catch {
    // ignore ffprobe discovery failures
  }
  return ''
}

async function probeVideoDuration(targetPath: string, ffprobePath: string): Promise<number> {
  if (!ffprobePath || !fs.existsSync(ffprobePath)) {
    return 0
  }
  return new Promise<number>((resolve) => {
    const child = spawn(
      ffprobePath,
      ['-v', 'error', '-show_entries', 'format=duration', '-of', 'default=nw=1:nk=1', targetPath],
      {
        cwd: getProjectRootPath(),
        windowsHide: true,
        stdio: ['ignore', 'pipe', 'ignore'],
      },
    )
    let stdout = ''
    child.stdout?.on('data', (chunk) => {
      stdout += String(chunk || '')
    })
    child.on('error', () => resolve(0))
    child.on('close', () => {
      const parsed = Number.parseFloat(String(stdout || '').trim() || '0')
      resolve(Number.isFinite(parsed) ? Math.max(0, parsed) : 0)
    })
  })
}

function shuffleInPlace<T>(items: T[]): void {
  for (let index = items.length - 1; index > 0; index -= 1) {
    const swapIndex = Math.floor(Math.random() * (index + 1))
    ;[items[index], items[swapIndex]] = [items[swapIndex], items[index]]
  }
}

async function writeMergeOrderLog(targetPath: string, originalOrder: string[], shuffledOrder: string[]): Promise<void> {
  try {
    const now = new Date()
    const stamp = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}-${String(now.getHours()).padStart(2, '0')}${String(now.getMinutes()).padStart(2, '0')}${String(now.getSeconds()).padStart(2, '0')}-${String(now.getMilliseconds()).padStart(3, '0')}`
    const orderPath = path.join(path.dirname(targetPath), `MERGE_ORDER_${stamp}.txt`)
    await fs.promises.writeFile(
      orderPath,
      `ORIGINAL:\n${originalOrder.join('\n')}\n\nSHUFFLED:\n${shuffledOrder.join('\n')}\n`,
      'utf8',
    )
  } catch {
    // ignore order-log write failures
  }
}

async function prepareMergeInputs(validPaths: string[], tempDir: string): Promise<string[]> {
  const prepared: string[] = []
  for (let index = 0; index < validPaths.length; index += 1) {
    const srcPath = validPaths[index]
    const targetPath = path.join(tempDir, `${String(index + 1).padStart(4, '0')}.mp4`)
    try {
      await fs.promises.link(srcPath, targetPath)
    } catch {
      await fs.promises.copyFile(srcPath, targetPath)
    }
    prepared.push(targetPath.replace(/\\/g, '/'))
  }
  return prepared
}

async function mergeVideoOutputs(options: {
  ffmpegPath: string
  mp4Paths: string[]
  targetPath: string
  onProgress: (message: string) => void
}): Promise<string | null> {
  const requestedPaths = options.mp4Paths.map((filePath) => String(filePath || '').trim()).filter(Boolean)
  if (requestedPaths.length < 2) {
    return null
  }
  if (isValidExportOutput(options.targetPath)) {
    return options.targetPath
  }

  await fs.promises.mkdir(path.dirname(options.targetPath), { recursive: true })
  const ffprobePath = resolveFfprobePath(options.ffmpegPath)
  const validPaths: string[] = []
  const skippedPaths: string[] = []
  for (const filePath of requestedPaths) {
    try {
      const stat = await fs.promises.stat(filePath)
      if (!stat.isFile() || stat.size < 50_000) {
        skippedPaths.push(filePath)
        continue
      }
      if (!(await isFileStable(filePath))) {
        skippedPaths.push(filePath)
        continue
      }
      if (ffprobePath) {
        const duration = await probeVideoDuration(filePath, ffprobePath)
        if (duration <= 0.05) {
          skippedPaths.push(filePath)
          continue
        }
      }
      validPaths.push(filePath)
    } catch {
      skippedPaths.push(filePath)
    }
  }
  if (skippedPaths.length) {
    const shown = skippedPaths
      .slice(0, 8)
      .map((filePath) => path.basename(filePath))
      .join(', ')
    const extra = skippedPaths.length > 8 ? ` (+${skippedPaths.length - 8} more)` : ''
    options.onProgress(`Skipping ${skippedPaths.length} incomplete MP4 file(s): ${shown}${extra}`)
  }
  if (validPaths.length < 2) {
    return null
  }

  const originalOrder = validPaths.map((filePath) => path.basename(filePath))
  shuffleInPlace(validPaths)
  await writeMergeOrderLog(
    options.targetPath,
    originalOrder,
    validPaths.map((filePath) => path.basename(filePath)),
  )

  const tempDir = await fs.promises.mkdtemp(path.join(path.dirname(options.targetPath), 'camxora-merge-'))
  const preparedInputs = await prepareMergeInputs(validPaths, tempDir)
  const concatFilePath = path.join(tempDir, 'merge-list.txt')
  const concatContents = ['ffconcat version 1.0', ...preparedInputs.map((filePath) => `file '${escapeFfconcatPath(filePath)}'`)].join('\n')
  await fs.promises.writeFile(concatFilePath, `${concatContents}\n`, 'utf8')

  const runFfmpeg = (args: string[]) =>
    new Promise<void>((resolve, reject) => {
      options.onProgress('Preparing FFmpeg merge…')
      const child = spawn(options.ffmpegPath, args, {
        cwd: getProjectRootPath(),
        windowsHide: true,
        stdio: ['ignore', 'pipe', 'pipe'],
      })
      activeVideoExport.activeJobs.set(`__merge__${options.targetPath}`, child)
      let stderr = ''
      child.stderr?.on('data', (chunk) => {
        stderr += String(chunk || '')
      })
      child.on('error', (error) => {
        activeVideoExport.activeJobs.delete(`__merge__${options.targetPath}`)
        reject(error)
      })
      child.on('close', (code) => {
        activeVideoExport.activeJobs.delete(`__merge__${options.targetPath}`)
        if (code === 0) {
          resolve()
          return
        }
        reject(new Error((stderr || '').trim() || `Video merge exited with code ${code}`))
      })
    })

  try {
    await runFfmpeg(['-y', '-f', 'concat', '-safe', '0', '-i', concatFilePath, '-c', 'copy', options.targetPath])
    if (isValidExportOutput(options.targetPath)) {
      return options.targetPath
    }
    options.onProgress('FFmpeg copy merge failed, retrying with re-encode…')
    await runFfmpeg([
      '-y',
      '-f',
      'concat',
      '-safe',
      '0',
      '-i',
      concatFilePath,
      '-c:v',
      'libx264',
      '-c:a',
      'aac',
      '-movflags',
      '+faststart',
      options.targetPath,
    ])
    if (!isValidExportOutput(options.targetPath)) {
      throw new Error('Merged output is missing or invalid.')
    }
    return options.targetPath
  } finally {
    try {
      await fs.promises.rm(tempDir, { recursive: true, force: true })
    } catch {
      // ignore temp cleanup failures
    }
  }
}

async function runSingleVideoExportJob(options: {
  mp3Path: string
  backgroundPath: string
  logoPath: string
  outputDir: string
  branch: VideoExportBranch
  width: number
  height: number
  ffmpegPath: string
  speedMode: string
  template: Record<string, unknown>
  pythonCommand: string
  pythonArgsPrefix: string[]
  onProgress: (message: string) => void
}): Promise<string> {
  const stem = path.parse(options.mp3Path).name
  const longOutputPath = path.join(options.outputDir, `${stem}.mp4`)
  const finalOutputPath =
    options.branch === 'reel' ? path.join(options.outputDir, `${stem}_REEL.mp4`) : longOutputPath
  if (isValidExportOutput(finalOutputPath)) {
    return finalOutputPath
  }

  const backupPath = `${longOutputPath}._std_backup`
  let backedUpStandard = false
  if (options.branch === 'reel' && fs.existsSync(longOutputPath)) {
    fs.renameSync(longOutputPath, backupPath)
    backedUpStandard = true
  }

  try {
    await new Promise<void>((resolve, reject) => {
      let stdoutBuffer = ''
      let stderr = ''
      const child = spawn(
        options.pythonCommand,
        [
          ...options.pythonArgsPrefix,
          '-m',
          'python_app.visualizer.main',
          options.mp3Path,
          'unused_template.json',
          '--templateB64',
          Buffer.from(JSON.stringify(options.template), 'utf8').toString('base64'),
          '--background',
          options.backgroundPath,
          '--logo',
          options.logoPath,
          '--outputDir',
          options.outputDir,
          '--ffmpeg',
          options.ffmpegPath,
          '--renderer',
          'gpu',
          '--speedMode',
          options.speedMode,
          '--fps',
          '30',
          '--width',
          String(options.width),
          '--height',
          String(options.height),
        ],
        {
          cwd: getProjectRootPath(),
          windowsHide: true,
          stdio: ['ignore', 'pipe', 'pipe'],
        },
      )

      activeVideoExport.activeJobs.set(options.mp3Path, child)

      const handleStdoutChunk = (chunk: unknown) => {
        stdoutBuffer += String(chunk || '')
        const lines = stdoutBuffer.split(/\r?\n/)
        stdoutBuffer = lines.pop() ?? ''
        lines.forEach((line) => {
          const trimmed = line.trim()
          if (!trimmed.startsWith('MG_EVENT ')) {
            return
          }
          try {
            const payload = JSON.parse(trimmed.slice('MG_EVENT '.length))
            if (payload?.status === 'running' && typeof payload.progress === 'number') {
              options.onProgress(`${Math.round(Number(payload.progress) * 100)}%`)
            }
          } catch {
            // ignore malformed progress lines
          }
        })
      }

      child.stdout?.on('data', handleStdoutChunk)
      child.stderr?.on('data', (chunk) => {
        stderr += String(chunk || '')
      })
      child.on('error', (error) => {
        activeVideoExport.activeJobs.delete(options.mp3Path)
        reject(error)
      })
      child.on('close', (code) => {
        activeVideoExport.activeJobs.delete(options.mp3Path)
        if (code === 0) {
          resolve()
          return
        }
        reject(new Error((stderr || '').trim() || `Video export exited with code ${code}`))
      })
    })

    if (options.branch === 'reel') {
      if (!fs.existsSync(longOutputPath)) {
        throw new Error(`Reel export did not produce ${path.basename(longOutputPath)}`)
      }
      fs.renameSync(longOutputPath, finalOutputPath)
    }

    if (!isValidExportOutput(finalOutputPath)) {
      throw new Error(`Video export did not produce a valid output for ${path.basename(options.mp3Path)}`)
    }
    return finalOutputPath
  } finally {
    if (backedUpStandard && fs.existsSync(backupPath)) {
      try {
        fs.renameSync(backupPath, longOutputPath)
      } catch {
        // ignore restore failures
      }
    }
  }
}

async function startVideoPipelineExport(request: VideoPipelineExportRequest): Promise<VideoWorkspaceState> {
  if (activeVideoExport.running) {
    return readVideoWorkspaceState()
  }

  const normalizedRunDir = String(request.runDir || '').trim()
  const normalizedBackgroundPath = String(request.backgroundPath || '').trim()
  const branch: VideoExportBranch = request.branch === 'reel' ? 'reel' : 'long'
  const batchId = String(request.batchId || '').trim()
  const role = String(request.role || '').trim()
  if (!normalizedRunDir || !fs.existsSync(normalizedRunDir)) {
    throw new Error('Selected run directory is missing.')
  }
  if (!normalizedBackgroundPath || !fs.existsSync(normalizedBackgroundPath)) {
    throw new Error('Selected branch background image is missing.')
  }

  const settings = resolvePipelineExportSettings(request)
  const workspace = readVideoWorkspaceState()
  const mp3List = listMp3Files(normalizedRunDir)
  if (!mp3List.length) {
    throw new Error('No MP3 files were found in the selected run directory.')
  }
  if (!isRecord(workspace.template) || !Object.keys(workspace.template).length) {
    throw new Error('No active video template is loaded.')
  }

  const { command: pythonCommand, argsPrefix: pythonArgsPrefix } = resolvePythonCommand(settings)
  const ffmpegPath = getStringSetting(settings, 'ffmpegPath', 'ffmpeg')
  const speedMode = getStringSetting(settings, 'videoExportSpeedMode', 'balanced')
  const configuredWorkers = Math.max(1, Math.min(10, getNumberSetting(settings, 'videoExportWorkers', 1)))
  const workers = Math.min(configuredWorkers, mp3List.length)
  const resolution = branch === 'reel' ? { width: 1080, height: 1920 } : parseResolution(workspace.outputResolution)
  const autoMergeEnabled = resolvePipelineAutoMerge(request, settings, branch)

  activeVideoExport.running = true
  activeVideoExport.branch = branch
  activeVideoExport.runDir = normalizedRunDir
  activeVideoExport.outputDir = normalizedRunDir
  activeVideoExport.workers = workers
  activeVideoExport.autoMerge = autoMergeEnabled
  activeVideoExport.mergeRunning = false
  activeVideoExport.currentStatus = `Starting ${branch === 'long' ? 'long' : 'reel'} export…`
  activeVideoExport.totalJobs = mp3List.length
  activeVideoExport.completedJobs = 0
  activeVideoExport.lastOutputPath = null
  activeVideoExport.lastMergedOutputPath = null
  activeVideoExport.selectedMp3Path = mp3List[0]?.path ?? ''
  activeVideoExport.mp3List = mp3List
  activeVideoExport.queue = mp3List.map((item) => item.path)
  activeVideoExport.activeJobs.clear()
  activeVideoExport.stopRequested = false
  emitVideoWorkspaceEvent('export', 30)

  const queue = [...mp3List]
  const failures: string[] = []
  const template = workspace.template
  const logoPath = String(workspace.logoPath || '').trim()

  const workerLoop = async () => {
    while (queue.length && !activeVideoExport.stopRequested && failures.length === 0) {
      const next = queue.shift()
      if (!next) {
        return
      }
      const index = activeVideoExport.completedJobs + activeVideoExport.activeJobs.size + 1
      activeVideoExport.selectedMp3Path = next.path
      activeVideoExport.currentStatus = `Exporting ${branch === 'long' ? 'Long' : 'Reel'} ${index}/${mp3List.length} · ${next.name}`
      emitVideoWorkspaceEvent('export', 120)
      try {
        const outputPath = await runSingleVideoExportJob({
          mp3Path: next.path,
          backgroundPath: normalizedBackgroundPath,
          logoPath,
          outputDir: normalizedRunDir,
          branch,
          width: resolution.width,
          height: resolution.height,
          ffmpegPath,
          speedMode,
          template,
          pythonCommand,
          pythonArgsPrefix,
          onProgress: (message) => {
            activeVideoExport.currentStatus = `Exporting ${branch === 'long' ? 'Long' : 'Reel'} ${index}/${mp3List.length} · ${message}`
            emitVideoWorkspaceEvent('export', 180)
          },
        })
        activeVideoExport.completedJobs += 1
        activeVideoExport.lastOutputPath = outputPath
        activeVideoExport.currentStatus = `Exported ${activeVideoExport.completedJobs}/${mp3List.length} ${branch === 'long' ? 'long' : 'reel'} video(s).`
        emitVideoWorkspaceEvent('export', 120)
      } catch (error) {
        if (activeVideoExport.stopRequested) {
          return
        }
        failures.push(error instanceof Error ? error.message : 'Video export failed.')
      }
    }
  }

  void Promise.all(Array.from({ length: workers }, () => workerLoop())).then(() => {
    if (activeVideoExport.stopRequested) {
      resetActiveVideoExportState('Video export stopped.')
      return
    }
    if (failures.length) {
      resetActiveVideoExportState(failures[0] || 'Video export failed.')
      return
    }
    const completed = mp3List.length
    const finish = async () => {
      if (activeVideoExport.autoMerge) {
        activeVideoExport.mergeRunning = true
        activeVideoExport.currentStatus = `Merging ${branch === 'long' ? 'long' : 'reel'} video outputs…`
        emitVideoWorkspaceEvent('export', 120)
        try {
          const branchOutputs = listBranchExportOutputs(normalizedRunDir, branch)
          const mergedTargetPath = buildMergedOutputPath(normalizedRunDir, batchId, role, branch)
          const mergedPath = await mergeVideoOutputs({
            ffmpegPath,
            mp4Paths: branchOutputs,
            targetPath: mergedTargetPath,
            onProgress: (message) => {
              activeVideoExport.currentStatus = message
              emitVideoWorkspaceEvent('export', 180)
            },
          })
          if (mergedPath) {
            activeVideoExport.lastMergedOutputPath = mergedPath
            resetActiveVideoExportState(
              `Export and merge complete · ${completed}/${completed} ${branch === 'long' ? 'long' : 'reel'} video(s).`,
            )
            return
          }
          resetActiveVideoExportState(
            `Export complete · ${completed}/${completed} ${branch === 'long' ? 'long' : 'reel'} video(s). Merge skipped because at least two valid MP4 files are required.`,
          )
          return
        } catch (error) {
          resetActiveVideoExportState(
            error instanceof Error ? error.message : 'Video merge failed.',
          )
          return
        }
      }
      resetActiveVideoExportState(
        `Export complete · ${completed}/${completed} ${branch === 'long' ? 'long' : 'reel'} video(s).`,
      )
    }
    void finish()
  })

  return readVideoWorkspaceState()
}

async function startManualVideoExport(request: ManualVideoExportRequest): Promise<VideoWorkspaceState> {
  if (activeVideoExport.running) {
    return readVideoWorkspaceState()
  }

  const scene = isRecord(request?.scene) ? request.scene : null
  const assets = scene && isRecord(scene.assets) ? scene.assets : null
  const output = scene && isRecord(scene.output) ? scene.output : null
  const audioPath = typeof assets?.audioPath === 'string' ? assets.audioPath.trim() : ''

  if (!scene || scene.mode !== 'manual') {
    throw new Error('Manual export request is invalid.')
  }
  if (!audioPath) {
    throw new Error('Manual export requires a selected audio track.')
  }
  if (!output || !Number.isFinite(Number(output.width)) || !Number.isFinite(Number(output.height))) {
    throw new Error('Manual export requires a valid output resolution.')
  }

  activeVideoExport.running = true
  activeVideoExport.branch = null
  activeVideoExport.runDir = null
  activeVideoExport.outputDir = null
  activeVideoExport.workers = 1
  activeVideoExport.autoMerge = false
  activeVideoExport.mergeRunning = false
  activeVideoExport.totalJobs = 1
  activeVideoExport.completedJobs = 0
  activeVideoExport.startedAtMs = null
  activeVideoExport.lastProgressEventAtMs = 0
  activeVideoExport.lastOutputPath = null
  activeVideoExport.lastMergedOutputPath = null
  activeVideoExport.currentOutputPath = null
  activeVideoExport.selectedMp3Path = audioPath
  activeVideoExport.outputDir = resolveManualVideoExportOutputDir(scene as ManualVideoExportRequest['scene'])
  activeVideoExport.mp3List = [
    {
      name: path.basename(audioPath),
      path: audioPath,
    },
  ]
  activeVideoExport.queue = []
  activeVideoExport.stopRequested = false
  activeVideoExport.currentStatus = 'Opening manual WebGPU export host…'
  activeVideoExportHost.pendingScene = scene as ManualVideoExportRequest['scene']
  activeVideoExportHost.currentScene = scene as ManualVideoExportRequest['scene']
  activeVideoExportHost.captureProbeRunning = false
  emitVideoWorkspaceEvent('export', 20)

  try {
    await ensureVideoExportHostWindow()
    if (flushPendingVideoExportHostScene()) {
      sendCommandToVideoExportHost({ type: 'stop' })
      activeVideoExport.currentStatus = 'Manual WebGPU export scene dispatched to the hidden host.'
      emitVideoWorkspaceEvent('export', 20)
    }
    return readVideoWorkspaceState()
  } catch (error) {
    resetVideoExportHostSessionState()
    clearManualVideoExportBootstrap(
      error instanceof Error ? error.message : 'Unable to start the manual WebGPU export host.',
    )
    emitVideoWorkspaceEvent('export', 20)
    throw error
  }

}

function stopVideoExport(): VideoWorkspaceState {
  if (activeVideoExport.branch === null && (activeVideoExport.running || activeVideoExportHost.pendingScene)) {
    resetVideoExportHostSessionState()
    if (videoExportHostWindow && !videoExportHostWindow.isDestroyed()) {
      const hostWindow = videoExportHostWindow
      videoExportHostWindow = null
      hostWindow.close()
    }
    clearManualVideoExportBootstrap('Manual WebGPU export bootstrap stopped.')
    emitVideoWorkspaceEvent('export', 20)
    return readVideoWorkspaceState()
  }

  if (!activeVideoExport.running) {
    return readVideoWorkspaceState()
  }
  activeVideoExport.stopRequested = true
  activeVideoExport.currentStatus = 'Stopping video export…'
  activeVideoExport.queue = []
  activeVideoExport.activeJobs.forEach((child) => {
    try {
      child.kill()
    } catch {
      // ignore kill failures
    }
  })
  if (activeVideoExport.activeJobs.size === 0) {
    resetActiveVideoExportState('Video export stopped.')
  }
  emitVideoWorkspaceEvent('export', 60)
  return readVideoWorkspaceState()
}

function emitVideoPreviewEvent(payload: VideoPreviewEventPayload): void {
  activeVideoPreview.currentEvent = payload
  if (!mainWindow || mainWindow.isDestroyed()) {
    return
  }
  mainWindow.webContents.send('video-preview:event', payload)
}

function emitVideoPyWorkspaceEvent(payload: VideoPyWorkspaceEventPayload): void {
  activeVideoPyWorkspace.currentEvent = payload
  if (!mainWindow || mainWindow.isDestroyed()) {
    return
  }
  mainWindow.webContents.send('video-py:event', payload)
}

let videoWorkspaceEventTimer: NodeJS.Timeout | null = null

function emitVideoWorkspaceEvent(reason: 'template' | 'output' | 'export', debounceMs = 0): void {
  if (!mainWindow || mainWindow.isDestroyed()) {
    return
  }

  const sendPayload = () => {
    videoWorkspaceEventTimer = null
    if (!mainWindow || mainWindow.isDestroyed()) {
      return
    }
    mainWindow.webContents.send('video:workspace-event', {
      reason,
      timestamp: Date.now(),
    })
  }

  if (debounceMs <= 0) {
    sendPayload()
    return
  }

  if (videoWorkspaceEventTimer != null) {
    clearTimeout(videoWorkspaceEventTimer)
  }
  videoWorkspaceEventTimer = setTimeout(sendPayload, debounceMs)
}

function hwndFromNativeHandle(handle: Buffer): number {
  if (!handle.length) {
    return 0
  }
  if (handle.length >= 8) {
    try {
      return Number(handle.readBigUInt64LE(0))
    } catch {
      return Number(handle.readUInt32LE(0))
    }
  }
  return Number(handle.readUInt32LE(0))
}

function sendVideoPreviewCommand(command: Record<string, unknown>): boolean {
  const child = activeVideoPreview.child
  if (!child?.stdin || child.stdin.destroyed) {
    return false
  }
  try {
    child.stdin.write(`${JSON.stringify(command)}\n`)
    return true
  } catch {
    return false
  }
}

function readVideoPyWorkspaceState(): { running: boolean; embedded: boolean; pid: number | null } {
  return {
    running: activeVideoPyWorkspace.running,
    embedded: activeVideoPyWorkspace.embedded,
    pid: activeVideoPyWorkspace.child?.pid ?? null,
  }
}

function sendVideoPyWorkspaceCommand(command: Record<string, unknown>): boolean {
  const child = activeVideoPyWorkspace.child
  if (!child?.stdin || child.stdin.destroyed) {
    return false
  }
  try {
    child.stdin.write(`${JSON.stringify(command)}\n`)
    return true
  } catch {
    return false
  }
}

async function openVideoPreview(payload: {
  template: Record<string, unknown>
  backgroundPath?: string
  logoPath?: string
  outputResolution?: string
}): Promise<boolean> {
  if (activeVideoPreview.running) {
    try {
      sendVideoPreviewCommand({
        templateB64: Buffer.from(JSON.stringify(payload.template ?? {}), 'utf8').toString('base64'),
      })
      setVideoPreviewAssets({
        backgroundPath: payload.backgroundPath,
        logoPath: payload.logoPath,
        audioPath: 'synthetic',
      })
      if (activeVideoPreview.bounds) {
        setVideoPreviewHostBounds(activeVideoPreview.bounds)
      }
      if (activeVideoPreview.currentEvent) {
        emitVideoPreviewEvent(activeVideoPreview.currentEvent)
      }
    } catch {
      // ignore update failures
    }
    return true
  }

  const settings = parseDefaultSettings()
  const { command: pythonCommand, argsPrefix: pythonArgsPrefix } = resolvePythonCommand(settings)
  const requestedResolution = String(payload.outputResolution || '').trim()
  const { width, height } = requestedResolution ? parseResolution(requestedResolution) : parseResolution('1920x1080')
  const backgroundPath = String(payload.backgroundPath || '').trim()
  const logoPath = String(payload.logoPath || '').trim()

  let stdoutBuffer = ''
  let stderr = ''

  const child = spawn(
    pythonCommand,
    [
      ...pythonArgsPrefix,
      '-m',
      'python_app.visualizer.main',
      'synthetic',
      'unused_template.json',
      '--templateB64',
      Buffer.from(JSON.stringify(payload.template ?? {}), 'utf8').toString('base64'),
      '--background',
      backgroundPath,
      '--logo',
      logoPath,
      '--renderer',
      'gpu',
      '--fps',
      '60',
      '--width',
      String(width),
      '--height',
      String(height),
      '--livePreview',
    ],
    {
      cwd: getProjectRootPath(),
      windowsHide: true,
      stdio: ['pipe', 'pipe', 'pipe'],
    },
  )

  activeVideoPreview.running = true
  activeVideoPreview.embedded = false
  activeVideoPreview.child = child

  emitVideoPreviewEvent({ status: 'opening', message: 'Starting embedded preview…' })

  const handleStdoutChunk = (chunk: unknown) => {
    stdoutBuffer += String(chunk || '')
    const lines = stdoutBuffer.split(/\r?\n/)
    stdoutBuffer = lines.pop() ?? ''
    lines.forEach((line) => {
      const trimmed = line.trim()
      if (!trimmed.startsWith('MG_EVENT ')) {
        return
      }
      try {
        const payload = JSON.parse(trimmed.slice('MG_EVENT '.length)) as VideoPreviewEventPayload
        emitVideoPreviewEvent(payload)
      } catch {
        // ignore malformed event lines
      }
    })
  }

  child.stdout?.on('data', handleStdoutChunk)
  child.stderr?.on('data', (chunk) => {
    stderr += String(chunk || '')
  })
  child.stdin?.on('error', () => {
    emitVideoPreviewEvent({
      status: 'error',
      message: 'Preview connection closed unexpectedly. The app stayed open so the preview can recover.',
    })
  })
  child.on('error', (error) => {
    activeVideoPreview.running = false
    activeVideoPreview.embedded = false
    activeVideoPreview.child = null
    activeVideoPreview.currentEvent = null
    emitVideoPreviewEvent({ status: 'error', message: error instanceof Error ? error.message : 'Preview process failed to start.' })
  })
  child.on('close', (code) => {
    activeVideoPreview.running = false
    activeVideoPreview.embedded = false
    activeVideoPreview.child = null
    activeVideoPreview.bounds = null
    activeVideoPreview.currentEvent = null
    emitVideoPreviewEvent({
      status: 'closed',
      message: code === 0 ? 'Preview closed.' : (stderr || '').trim() || `Preview exited with code ${code ?? 0}`,
    })
  })

  if (activeVideoPreview.bounds) {
    const parentHwnd = mainWindow ? hwndFromNativeHandle(mainWindow.getNativeWindowHandle()) : 0
    if (parentHwnd) {
      sendVideoPreviewCommand({ cmd: 'embed', parentHwnd })
      activeVideoPreview.embedded = true
    }
    sendVideoPreviewCommand({ cmd: 'setBounds', ...activeVideoPreview.bounds })
  }

  return true
}

function closeVideoPreview(): boolean {
  if (!activeVideoPreview.running) {
    return true
  }

  sendVideoPreviewCommand({ cmd: 'exit' })
  const child = activeVideoPreview.child
  if (child) {
    try {
      child.kill()
    } catch {
      // ignore kill failures
    }
  }
  activeVideoPreview.running = false
  activeVideoPreview.embedded = false
  activeVideoPreview.child = null
  activeVideoPreview.bounds = null
  activeVideoPreview.currentEvent = null
  emitVideoPreviewEvent({ status: 'closed', message: 'Preview closed.' })
  return true
}

function setVideoPreviewHostBounds(bounds: VideoPreviewHostBounds): boolean {
  const normalized: VideoPreviewHostBounds = {
    x: Math.max(0, Math.round(Number(bounds?.x ?? 0))),
    y: Math.max(0, Math.round(Number(bounds?.y ?? 0))),
    width: Math.max(1, Math.round(Number(bounds?.width ?? 1))),
    height: Math.max(1, Math.round(Number(bounds?.height ?? 1))),
    dpr: Math.max(0.5, Math.min(5, Number(bounds?.dpr ?? 1))),
  }

  activeVideoPreview.bounds = normalized
  if (!activeVideoPreview.running) {
    return true
  }

  if (!activeVideoPreview.embedded) {
    const parentHwnd = mainWindow ? hwndFromNativeHandle(mainWindow.getNativeWindowHandle()) : 0
    if (parentHwnd) {
      sendVideoPreviewCommand({ cmd: 'embed', parentHwnd })
      activeVideoPreview.embedded = true
    }
  }

  sendVideoPreviewCommand({ cmd: 'setBounds', ...normalized })
  return true
}

function patchVideoPreviewTemplate(patch: Record<string, unknown>): boolean {
  if (!activeVideoPreview.running) {
    return false
  }
  const normalizedPatch = isRecord(patch) ? patch : {}
  return sendVideoPreviewCommand({ templatePatch: normalizedPatch })
}

function setVideoPreviewAssets(payload: { backgroundPath?: string; logoPath?: string; audioPath?: string }): boolean {
  if (!activeVideoPreview.running) {
    return false
  }
  const cmd: Record<string, unknown> = {}
  if (typeof payload.backgroundPath === 'string') {
    cmd.backgroundPath = payload.backgroundPath
  }
  if (typeof payload.logoPath === 'string') {
    cmd.logoPath = payload.logoPath
  }
  if (typeof payload.audioPath === 'string') {
    cmd.audioPath = payload.audioPath
  }
  if (!Object.keys(cmd).length) {
    return true
  }
  return sendVideoPreviewCommand(cmd)
}

async function openVideoPyWorkspace(): Promise<{ running: boolean; embedded: boolean; pid: number | null }> {
  if (activeVideoPyWorkspace.running) {
    if (activeVideoPyWorkspace.bounds) {
      setVideoPyWorkspaceHostBounds(activeVideoPyWorkspace.bounds)
    }
    if (activeVideoPyWorkspace.currentEvent) {
      emitVideoPyWorkspaceEvent(activeVideoPyWorkspace.currentEvent)
    }
    return readVideoPyWorkspaceState()
  }

  const settings = parseDefaultSettings()
  const { command: pythonCommand, argsPrefix: pythonArgsPrefix } = resolvePythonCommand(settings)
  let stdoutBuffer = ''
  let stderr = ''

  const child = spawn(
    pythonCommand,
    [...pythonArgsPrefix, '-m', 'python_app.standalone_video_workspace'],
    {
      cwd: getProjectRootPath(),
      windowsHide: true,
      stdio: ['pipe', 'pipe', 'pipe'],
    },
  )

  activeVideoPyWorkspace.running = true
  activeVideoPyWorkspace.embedded = false
  activeVideoPyWorkspace.child = child

  emitVideoPyWorkspaceEvent({ status: 'opening', message: 'Starting native Python video workspace…' })

  const handleStdoutChunk = (chunk: unknown) => {
    stdoutBuffer += String(chunk || '')
    const lines = stdoutBuffer.split(/\r?\n/)
    stdoutBuffer = lines.pop() ?? ''
    lines.forEach((line) => {
      const trimmed = line.trim()
      if (!trimmed.startsWith('MG_EVENT ')) {
        return
      }
      try {
        const payload = JSON.parse(trimmed.slice('MG_EVENT '.length)) as VideoPyWorkspaceEventPayload
        emitVideoPyWorkspaceEvent(payload)
      } catch {
        // ignore malformed event lines
      }
    })
  }

  child.stdout?.on('data', handleStdoutChunk)
  child.stderr?.on('data', (chunk) => {
    stderr += String(chunk || '')
  })
  child.stdin?.on('error', () => {
    emitVideoPyWorkspaceEvent({
      status: 'error',
      message: 'Video (Py) connection closed unexpectedly.',
    })
  })
  child.on('error', (error) => {
    activeVideoPyWorkspace.running = false
    activeVideoPyWorkspace.embedded = false
    activeVideoPyWorkspace.child = null
    activeVideoPyWorkspace.currentEvent = null
    emitVideoPyWorkspaceEvent({
      status: 'error',
      message: error instanceof Error ? error.message : 'Video (Py) process failed to start.',
    })
  })
  child.on('close', (code) => {
    activeVideoPyWorkspace.running = false
    activeVideoPyWorkspace.embedded = false
    activeVideoPyWorkspace.child = null
    activeVideoPyWorkspace.bounds = null
    activeVideoPyWorkspace.currentEvent = null
    emitVideoPyWorkspaceEvent({
      status: 'closed',
      message:
        code === 0 ? 'Video (Py) closed.' : (stderr || '').trim() || `Video (Py) exited with code ${code ?? 0}`,
    })
  })

  if (activeVideoPyWorkspace.bounds) {
    const parentHwnd = mainWindow ? hwndFromNativeHandle(mainWindow.getNativeWindowHandle()) : 0
    if (parentHwnd) {
      sendVideoPyWorkspaceCommand({ cmd: 'embed', parentHwnd })
      activeVideoPyWorkspace.embedded = true
    }
    sendVideoPyWorkspaceCommand({ cmd: 'setBounds', ...activeVideoPyWorkspace.bounds })
  }

  return readVideoPyWorkspaceState()
}

function closeVideoPyWorkspace(): { running: boolean; embedded: boolean; pid: number | null } {
  if (!activeVideoPyWorkspace.running) {
    return readVideoPyWorkspaceState()
  }

  sendVideoPyWorkspaceCommand({ cmd: 'exit' })
  const child = activeVideoPyWorkspace.child
  if (child) {
    try {
      child.kill()
    } catch {
      // ignore kill failures
    }
  }

  activeVideoPyWorkspace.running = false
  activeVideoPyWorkspace.embedded = false
  activeVideoPyWorkspace.child = null
  activeVideoPyWorkspace.bounds = null
  activeVideoPyWorkspace.currentEvent = null
  emitVideoPyWorkspaceEvent({ status: 'closed', message: 'Video (Py) closed.' })
  return readVideoPyWorkspaceState()
}

function setVideoPyWorkspaceHostBounds(bounds: VideoPreviewHostBounds): boolean {
  const normalized: VideoPreviewHostBounds = {
    x: Math.max(0, Math.round(Number(bounds?.x ?? 0))),
    y: Math.max(0, Math.round(Number(bounds?.y ?? 0))),
    width: Math.max(1, Math.round(Number(bounds?.width ?? 1))),
    height: Math.max(1, Math.round(Number(bounds?.height ?? 1))),
    dpr: Math.max(0.5, Math.min(5, Number(bounds?.dpr ?? 1))),
  }

  activeVideoPyWorkspace.bounds = normalized
  if (!activeVideoPyWorkspace.running) {
    return true
  }

  if (!activeVideoPyWorkspace.embedded) {
    const parentHwnd = mainWindow ? hwndFromNativeHandle(mainWindow.getNativeWindowHandle()) : 0
    if (parentHwnd) {
      sendVideoPyWorkspaceCommand({ cmd: 'embed', parentHwnd })
      activeVideoPyWorkspace.embedded = true
    }
  }

  sendVideoPyWorkspaceCommand({ cmd: 'setBounds', ...normalized })
  return true
}

function buildFallbackVideoWorkspaceState(note: string): VideoWorkspaceState {
  return {
    template: {},
    templateId: null,
    templateName: 'No template loaded',
    templates: [],
    outputResolution: '1920x1080',
    previewAspectRatio: {
      width: 16,
      height: 9,
    },
    backgroundPath: '',
    logoPath: '',
    selectedMp3Path: '',
    mp3Directory: '',
    mp3List: [],
    playback: {
      isPlaying: false,
      isReady: false,
      isLoading: false,
      currentTimeSec: 0,
      durationSec: 0,
    },
    export: {
      running: false,
      branch: null,
      workers: 1,
      autoMerge: false,
      mergeRunning: false,
      currentStatus: 'Video workspace bootstrap is unavailable.',
      outputDir: null,
      totalJobs: 0,
      completedJobs: 0,
      lastOutputPath: null,
      lastMergedOutputPath: null,
    },
    ui: {
      previewTitle: 'Preview: unavailable',
      livePreviewOpen: false,
      source: 'fallback',
      notes: [note],
    },
  }
}

function readVideoWorkspaceState(): VideoWorkspaceState {
  const templates = readJsonFile<VideoTemplateRecord[]>(getVideoTemplatesPath()) ?? []
  const settings = parseDefaultSettings() ?? {}
  const prefs = readVideoWorkspacePrefs()
  const templateId =
    String(prefs.templateId ?? settings.videoRenderTemplatePath ?? '').trim() || null
  const selectedTemplate =
    (templateId ? templates.find((template) => template.id === templateId) : null) ?? templates[0] ?? null
  const template = selectedTemplate?.template ?? {}
  const templateName = String(
    (template.templateName as string | undefined) ??
      selectedTemplate?.name ??
      'No template loaded',
  ).trim() || 'No template loaded'
  const outputResolution =
    String(settings.outputResolution ?? '1920x1080').trim() || '1920x1080'
  const parsedResolution = parseResolution(outputResolution)
  const exportProgressPercent = computeVideoExportProgressPercent(
    activeVideoExport.completedJobs,
    activeVideoExport.totalJobs,
  )
  const exportEstimatedRemainingSec = computeVideoExportEstimatedRemainingSec(
    activeVideoExport.startedAtMs,
    activeVideoExport.completedJobs,
    activeVideoExport.totalJobs,
  )
  const backgroundPath = String(
    prefs.backgroundPath ?? settings.videoRenderBackgroundPath ?? template.previewBackground ?? '',
  ).trim()
  const logoPath = String(prefs.logoPath ?? settings.videoRenderLogoPath ?? template.logoPath ?? '').trim()
  const preferredMp3Path = String(prefs.selectedMp3Path ?? '').trim()
  const exportWorkersRaw = Number(settings.videoExportWorkers ?? settings.perfMergeWorkers ?? 1)
  const workspaceMp3 = resolveWorkspaceMp3Selection(preferredMp3Path)

  if (!templates.length) {
    return {
      ...buildFallbackVideoWorkspaceState(
        'No local Python video templates were found. The read-only bridge is waiting for template data.',
      ),
      outputResolution,
      previewAspectRatio: parsedResolution,
      export: {
        running: false,
        branch: null,
        workers: Number.isFinite(exportWorkersRaw) && exportWorkersRaw > 0 ? exportWorkersRaw : 1,
        autoMerge: Boolean(settings.autoMergeAfterVideo ?? false),
        mergeRunning: false,
        currentStatus: 'No local templates available yet.',
        outputDir: String(settings.videoRenderOutputDir ?? '').trim() || null,
        currentOutputPath: null,
        totalJobs: 0,
        completedJobs: 0,
        progressPercent: 0,
        estimatedRemainingSec: null,
        startedAtMs: null,
        lastOutputPath: null,
        lastMergedOutputPath: null,
      },
    }
  }

  return {
    template,
    templateId: selectedTemplate?.id ?? null,
    templateName,
    templates: templates.map((item) => ({
      id: item.id,
      name: item.name,
      kind: item.source ? String(item.source) : null,
      updatedAt: item.updated_at ?? null,
    })),
    outputResolution,
    previewAspectRatio: parsedResolution,
    backgroundPath,
    logoPath,
    selectedMp3Path: activeVideoExport.running ? activeVideoExport.selectedMp3Path : workspaceMp3.selectedMp3Path,
    mp3Directory: activeVideoExport.running ? activeVideoExport.runDir ?? '' : workspaceMp3.mp3Directory,
    mp3List: activeVideoExport.running ? activeVideoExport.mp3List : workspaceMp3.mp3List,
    playback: {
      isPlaying: false,
      isReady: false,
      isLoading: false,
      currentTimeSec: 0,
      durationSec: 0,
    },
    export: {
      running: activeVideoExport.running,
      branch: activeVideoExport.branch,
      workers:
        activeVideoExport.running && activeVideoExport.workers > 0
          ? activeVideoExport.workers
          : Number.isFinite(exportWorkersRaw) && exportWorkersRaw > 0
            ? exportWorkersRaw
            : 1,
      autoMerge: activeVideoExport.running
        ? activeVideoExport.autoMerge
        : Boolean(settings.autoMergeAfterVideo ?? false),
      mergeRunning: activeVideoExport.mergeRunning,
      currentStatus: activeVideoExport.currentStatus || 'Read-only bootstrap loaded from local Python template/settings sources.',
      outputDir: activeVideoExport.outputDir ?? (String(settings.videoRenderOutputDir ?? '').trim() || null),
      currentOutputPath: activeVideoExport.currentOutputPath,
      totalJobs: activeVideoExport.totalJobs,
      completedJobs: activeVideoExport.completedJobs,
      progressPercent: exportProgressPercent,
      estimatedRemainingSec: exportEstimatedRemainingSec,
      startedAtMs: activeVideoExport.startedAtMs,
      lastOutputPath: activeVideoExport.lastOutputPath,
      lastMergedOutputPath: activeVideoExport.lastMergedOutputPath,
    },
    ui: {
      previewTitle: `Preview: ${templateName}`,
      livePreviewOpen: false,
      source: 'python-local',
      notes: [
        'This first Electron bridge loads local Python template/state sources only.',
        'Native live preview and playback transport still remain the next phase.',
      ],
    },
  }
}

function deleteVideoTemplate(templateId: string): VideoWorkspaceState {
  const normalizedTemplateId = String(templateId || '').trim()
  if (!normalizedTemplateId) {
    return readVideoWorkspaceState()
  }

  const templates = readJsonFile<VideoTemplateRecord[]>(getVideoTemplatesPath()) ?? []
  if (!templates.length) {
    return readVideoWorkspaceState()
  }

  const currentState = readVideoWorkspaceState()
  const deleteIndex = templates.findIndex((template) => template.id === normalizedTemplateId)
  if (deleteIndex < 0) {
    return currentState
  }

  templates.splice(deleteIndex, 1)
  writeJsonFile(getVideoTemplatesPath(), templates)

  const nextSelectedTemplateId =
    currentState.templateId && currentState.templateId !== normalizedTemplateId
      ? currentState.templateId
      : templates[Math.min(deleteIndex, templates.length - 1)]?.id ?? null

  const prefs = readVideoWorkspacePrefs()
  writeVideoWorkspacePrefs({
    ...prefs,
    templateId: nextSelectedTemplateId,
  })

  emitVideoWorkspaceEvent('template', 20)
  return readVideoWorkspaceState()
}

function registerIpcHandlers(): void {
  ipcMain.handle('app:get-meta', () => ({
    name: 'CAMXORA',
    version: app.getVersion(),
    isDev,
    platform: process.platform,
  }))

  ipcMain.handle('secure-storage:get', (_event, key: string) => {
    const store = readSecureStore()
    const value = store[key]
    return value ? decodeValue(value) : null
  })

  ipcMain.handle('secure-storage:set', (_event, key: string, value: string) => {
    const store = readSecureStore()
    store[key] = encodeValue(value)
    writeSecureStore(store)
    return true
  })

  ipcMain.handle('secure-storage:remove', (_event, key: string) => {
    const store = readSecureStore()
    delete store[key]
    writeSecureStore(store)
    return true
  })

  ipcMain.handle('secure-storage:clear', () => {
    writeSecureStore({})
    return true
  })

  ipcMain.handle(
    'files:select-file',
    async (
      event,
      options?: {
        title?: string
        filters?: Array<{ name: string; extensions: string[] }>
      },
    ) => {
      const owner = BrowserWindow.fromWebContents(event.sender) ?? mainWindow ?? null
      const result = owner
        ? await dialog.showOpenDialog(owner, {
            title: options?.title?.trim() || 'Select file',
            properties: ['openFile'],
            filters: Array.isArray(options?.filters) ? options.filters : undefined,
          })
        : await dialog.showOpenDialog({
        title: options?.title?.trim() || 'Select file',
        properties: ['openFile'],
        filters: Array.isArray(options?.filters) ? options.filters : undefined,
        })
      if (result.canceled) {
        return null
      }
      return result.filePaths[0] ?? null
    },
  )

  ipcMain.handle(
    'files:select-path',
    async (
      event,
      options?: {
        title?: string
        kind?: 'file' | 'directory'
        filters?: Array<{ name: string; extensions: string[] }>
      },
    ) => {
      const kind = options?.kind === 'directory' ? 'directory' : 'file'
      const owner = BrowserWindow.fromWebContents(event.sender) ?? mainWindow ?? null
      const dialogOptions = {
        title: options?.title?.trim() || (kind === 'directory' ? 'Select folder' : 'Select file'),
        properties: [kind === 'directory' ? 'openDirectory' : 'openFile'] as Array<'openFile' | 'openDirectory'>,
        filters: kind === 'file' && Array.isArray(options?.filters) ? options.filters : undefined,
      }
      const result = owner
        ? await dialog.showOpenDialog(owner, dialogOptions)
        : await dialog.showOpenDialog(dialogOptions)
      if (result.canceled) {
        return null
      }
      return result.filePaths[0] ?? null
    },
  )

  ipcMain.handle('files:read-file-as-base64', async (_event, targetPath: string) => {
    const normalizedPath = String(targetPath || '').trim()
    if (!normalizedPath) {
      return null
    }
    try {
      const stat = await fs.promises.stat(normalizedPath)
      if (!stat.isFile()) {
        return null
      }
      const fileBuffer = await fs.promises.readFile(normalizedPath)
      return fileBuffer.toString('base64')
    } catch {
      return null
    }
  })

  ipcMain.handle(
    'files:list-directory-entries',
    async (
      _event,
      options: {
        directoryPath: string
        maxResults?: number
      },
    ) => {
      const normalizedPath = String(options?.directoryPath || '').trim()
      if (!normalizedPath) {
        return []
      }
      try {
        const stat = await fs.promises.stat(normalizedPath)
        if (!stat.isDirectory()) {
          return []
        }
        const entries = await fs.promises.readdir(normalizedPath, { withFileTypes: true })
        return entries
          .sort((a, b) => a.name.localeCompare(b.name))
          .slice(0, Math.max(1, Math.min(1000, Number(options?.maxResults ?? 200))))
          .map((entry) => ({
            name: entry.name,
            isDirectory: entry.isDirectory(),
          }))
      } catch {
        return []
      }
    },
  )

  ipcMain.handle(
    'files:list-directory-images',
    async (
      _event,
      options: {
        directoryPath: string
        maxResults?: number
      },
    ) => {
      const normalizedPath = String(options?.directoryPath || '').trim()
      if (!normalizedPath) {
        return []
      }
      try {
        const stat = await fs.promises.stat(normalizedPath)
        if (!stat.isDirectory()) {
          return []
        }
        const entries = await fs.promises.readdir(normalizedPath, { withFileTypes: true })
        const allowedExt = new Set(['.png', '.jpg', '.jpeg', '.webp'])
        const results = entries
          .filter((entry) => entry.isFile())
          .map((entry) => entry.name)
          .filter((name) => allowedExt.has(path.extname(name).toLowerCase()))
          .sort((a, b) => a.localeCompare(b))
          .slice(0, Math.max(1, Math.min(500, Number(options?.maxResults ?? 200))))
          .map((name) => path.join(normalizedPath, name))
        return results
      } catch {
        return []
      }
    },
  )

  ipcMain.handle(
    'files:save-base64-file',
    async (
      event,
      options: {
        title?: string
        defaultPath?: string
        filters?: Array<{ name: string; extensions: string[] }>
        base64: string
      },
    ) => {
      const normalizedBase64 = String(options?.base64 || '').trim()
      if (!normalizedBase64) {
        return false
      }
      const owner = BrowserWindow.fromWebContents(event.sender) ?? mainWindow ?? null
      const saveResult = owner
        ? await dialog.showSaveDialog(owner, {
            title: options?.title?.trim() || 'Save file',
            defaultPath: options?.defaultPath?.trim() || undefined,
            filters: Array.isArray(options?.filters) ? options.filters : undefined,
          })
        : await dialog.showSaveDialog({
            title: options?.title?.trim() || 'Save file',
            defaultPath: options?.defaultPath?.trim() || undefined,
            filters: Array.isArray(options?.filters) ? options.filters : undefined,
          })
      if (saveResult.canceled || !saveResult.filePath) {
        return false
      }
      try {
        const fileBuffer = Buffer.from(normalizedBase64, 'base64')
        await fs.promises.writeFile(saveResult.filePath, fileBuffer)
        return true
      } catch {
        return false
      }
    },
  )

  ipcMain.handle('files:ensure-directory', async (_event, targetPath: string) => {
    const normalizedPath = String(targetPath || '').trim()
    if (!normalizedPath) {
      return false
    }
    try {
      await fs.promises.mkdir(normalizedPath, { recursive: true })
      return true
    } catch {
      return false
    }
  })

  ipcMain.handle('files:open-path', async (_event, targetPath: string) => {
    const normalizedPath = String(targetPath || '').trim()
    if (!normalizedPath) {
      return false
    }
    const result = await shell.openPath(normalizedPath)
    return result === ''
  })

  ipcMain.handle('files:open-external-url', async (_event, targetUrl: string) => {
    const normalizedUrl = String(targetUrl || '').trim()
    if (!normalizedUrl) {
      return false
    }
    try {
      await shell.openExternal(normalizedUrl)
      return true
    } catch {
      return false
    }
  })

  ipcMain.handle(
    'files:download-and-extract-zip',
    async (
      _event,
      options: {
        url: string
        destinationDir: string
      },
    ) => {
      const urlValue = String(options?.url || '').trim()
      const destinationDir = String(options?.destinationDir || '').trim()
      if (!urlValue) {
        return { ok: false, installedCount: 0, error: 'Missing download URL.' }
      }
      if (!destinationDir) {
        return { ok: false, installedCount: 0, error: 'Missing destination folder.' }
      }

      const resolvedDestination = path.resolve(destinationDir)
      try {
        await fs.promises.mkdir(resolvedDestination, { recursive: true })
        const stat = await fs.promises.stat(resolvedDestination)
        if (!stat.isDirectory()) {
          return { ok: false, installedCount: 0, error: 'Destination is not a folder.' }
        }
      } catch {
        return { ok: false, installedCount: 0, error: 'Unable to prepare destination folder.' }
      }

      const tempBase = path.join(os.tmpdir(), `camxora-pack-${Date.now()}-${Math.random().toString(16).slice(2)}`)
      const tempZip = `${tempBase}.zip`
      const tempExtractDir = `${tempBase}-extract`
      try {
        await downloadToFile(urlValue, tempZip)
        await fs.promises.mkdir(tempExtractDir, { recursive: true })
        const expandCommand = `Expand-Archive -LiteralPath ${escapePowerShellLiteral(tempZip)} -DestinationPath ${escapePowerShellLiteral(tempExtractDir)} -Force`
        await runPowerShell(expandCommand)

        const allowedExt = new Set(['.png', '.jpg', '.jpeg', '.webp'])
        const extractedFiles = await listFilesRecursive(tempExtractDir)
        const destRoot = resolvedDestination
        const destRootNormalized = destRoot.endsWith(path.sep) ? destRoot : `${destRoot}${path.sep}`
        let installedCount = 0

        for (const filePath of extractedFiles) {
          const ext = path.extname(filePath).toLowerCase()
          if (!allowedExt.has(ext)) {
            continue
          }
          const relative = path.relative(tempExtractDir, filePath)
          if (!relative || relative.startsWith('..') || path.isAbsolute(relative)) {
            continue
          }
          const targetPath = path.resolve(destRoot, relative)
          if (!(targetPath === destRoot || targetPath.startsWith(destRootNormalized))) {
            continue
          }
          await fs.promises.mkdir(path.dirname(targetPath), { recursive: true })
          await fs.promises.copyFile(filePath, targetPath)
          installedCount += 1
        }

        return { ok: true, installedCount }
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Unable to download and extract zip.'
        return { ok: false, installedCount: 0, error: message }
      } finally {
        try {
          await fs.promises.rm(tempZip, { force: true })
        } catch {
          // ignore
        }
        try {
          await fs.promises.rm(tempExtractDir, { recursive: true, force: true })
        } catch {
          // ignore
        }
      }
    },
  )

  ipcMain.handle(
    'files:download-music-tracks',
    async (
      _event,
      options: {
        items: MusicTrackDownloadRequest[]
        retryCount?: number
      },
    ): Promise<MusicTrackDownloadResult[]> => {
      const items = Array.isArray(options?.items) ? options.items : []
      const retryCount = Math.max(1, Math.min(5, Number(options?.retryCount ?? 3)))
      const results: MusicTrackDownloadResult[] = []
      for (const item of items) {
        results.push(await downloadMusicTrackWithRetry(item, retryCount))
      }
      return results
    },
  )

  ipcMain.handle('effect-packs:list-catalog', async () => {
    return listEffectPackCatalog({
      registryRoot: effectPackRegistryRoot,
      appVersion: app.getVersion(),
    })
  })

  ipcMain.handle('effect-packs:install-from-url', async (_event, options: { url: string }) => {
    const url = String(options?.url || '').trim()
    if (!url) {
      return { ok: false, item: null, replacedVersion: null, error: 'Missing effect-pack URL.' }
    }
    return installEffectPackFromUrl({
      registryRoot: effectPackRegistryRoot,
      appVersion: app.getVersion(),
      url,
      downloadToFile,
      expandZip: expandArchive,
    })
  })

  ipcMain.handle('effect-packs:install-from-file', async (_event, options: { zipPath: string }) => {
    const zipPath = String(options?.zipPath || '').trim()
    if (!zipPath) {
      return { ok: false, item: null, replacedVersion: null, error: 'Missing effect-pack file path.' }
    }
    return installEffectPackFromFile({
      registryRoot: effectPackRegistryRoot,
      appVersion: app.getVersion(),
      zipPath,
      expandZip: expandArchive,
    })
  })

  ipcMain.handle(
    'effect-packs:set-enabled',
    async (_event, options: { packId: string; enabled: boolean }) => {
      const packId = String(options?.packId || '').trim()
      if (!packId) {
        return { ok: false, item: null, error: 'Missing effect-pack id.' }
      }
      return setEffectPackEnabled({
        registryRoot: effectPackRegistryRoot,
        appVersion: app.getVersion(),
        packId,
        enabled: Boolean(options?.enabled),
      })
    },
  )

  ipcMain.handle(
    'effect-packs:activate-version',
    async (_event, options: { packId: string; version: string }) => {
      const packId = String(options?.packId || '').trim()
      const version = String(options?.version || '').trim()
      if (!packId || !version) {
        return { ok: false, item: null, error: 'Missing effect-pack version selection.' }
      }
      return activateEffectPackVersion({
        registryRoot: effectPackRegistryRoot,
        appVersion: app.getVersion(),
        packId,
        version,
      })
    },
  )

  ipcMain.handle(
    'effect-packs:remove-version',
    async (_event, options: { packId: string; version: string }) => {
      const packId = String(options?.packId || '').trim()
      const version = String(options?.version || '').trim()
      if (!packId || !version) {
        return { ok: false, removed: false, error: 'Missing effect-pack version selection.' }
      }
      return removeEffectPack({
        registryRoot: effectPackRegistryRoot,
        appVersion: app.getVersion(),
        packId,
        version,
      })
    },
  )

  ipcMain.handle('video:get-workspace-state', () => {
    return readVideoWorkspaceState()
  })

  ipcMain.handle('video:set-template', (_event, templateId: string) => {
    const nextTemplateId = String(templateId || '').trim()
    const state = readVideoWorkspaceState()
    const templateExists = state.templates.some((template) => template.id === nextTemplateId)
    if (!templateExists) {
      return state
    }

    const prefs = readVideoWorkspacePrefs()
    writeVideoWorkspacePrefs({
      ...prefs,
      templateId: nextTemplateId,
    })
    emitVideoWorkspaceEvent('template', 20)
    return readVideoWorkspaceState()
  })

  ipcMain.handle('video:set-output-resolution', (_event, resolution: string) => {
    const normalized = String(resolution || '').trim()
    if (!/^\d+x\d+$/i.test(normalized)) {
      return readVideoWorkspaceState()
    }

    const prefs = readVideoWorkspacePrefs()
    writeVideoWorkspacePrefs({
      ...prefs,
      outputResolution: normalized,
    })
    emitVideoWorkspaceEvent('output', 20)
    return readVideoWorkspaceState()
  })

  ipcMain.handle('video:set-background-path', (_event, backgroundPath: string) => {
    const prefs = readVideoWorkspacePrefs()
    writeVideoWorkspacePrefs({
      ...prefs,
      backgroundPath: String(backgroundPath || '').trim(),
    })
    emitVideoWorkspaceEvent('output', 20)
    return readVideoWorkspaceState()
  })

  ipcMain.handle('video:set-logo-path', (_event, logoPath: string) => {
    const prefs = readVideoWorkspacePrefs()
    writeVideoWorkspacePrefs({
      ...prefs,
      logoPath: String(logoPath || '').trim(),
    })
    emitVideoWorkspaceEvent('output', 20)
    return readVideoWorkspaceState()
  })

  ipcMain.handle('video:set-mp3-path', (_event, mp3Path: string) => {
    const normalizedPath = String(mp3Path || '').trim()
    const prefs = readVideoWorkspacePrefs()
    writeVideoWorkspacePrefs({
      ...prefs,
      selectedMp3Path: normalizedPath,
    })
    emitVideoWorkspaceEvent('output', 20)
    return readVideoWorkspaceState()
  })

  ipcMain.handle('video:patch-template', (_event, patch: Record<string, unknown>) => {
    const templates = readJsonFile<VideoTemplateRecord[]>(getVideoTemplatesPath()) ?? []
    if (!templates.length) {
      return readVideoWorkspaceState()
    }

    const currentState = readVideoWorkspaceState()
    const selectedTemplateId = currentState.templateId ?? currentState.templates[0]?.id ?? null
    if (!selectedTemplateId) {
      return currentState
    }

    const selectedIndex = templates.findIndex((template) => template.id === selectedTemplateId)
    if (selectedIndex < 0) {
      return currentState
    }

    const currentRecord = templates[selectedIndex]
    const currentTemplate = isRecord(currentRecord.template) ? currentRecord.template : {}
    const normalizedPatch = isRecord(patch) ? patch : {}
    const nextTemplate = mergeUnknown(currentTemplate, normalizedPatch)
    if (!isRecord(nextTemplate)) {
      return currentState
    }

    const nextTemplateName =
      String((nextTemplate.templateName as string | undefined) ?? currentRecord.name ?? '').trim() ||
      currentRecord.name ||
      'Untitled Template'

    templates[selectedIndex] = {
      ...currentRecord,
      name: nextTemplateName,
      template: nextTemplate,
      updated_at: new Date().toISOString().replace('T', ' ').replace('Z', ''),
    }

    writeJsonFile(getVideoTemplatesPath(), templates)
    emitVideoWorkspaceEvent('template', 20)
    return readVideoWorkspaceState()
  })

  ipcMain.handle('video:get-audio-analysis-cache', async (_event, request: { sourcePath: string }) => {
    const cachePath = await resolveVideoAudioAnalysisCachePath(request?.sourcePath ?? '')
    if (!cachePath) {
      return null
    }
    try {
      return await fs.promises.readFile(cachePath, 'utf8')
    } catch {
      return null
    }
  })

  ipcMain.handle(
    'video:set-audio-analysis-cache',
    async (_event, request: { sourcePath: string; payload: string }) => {
      const cachePath = await resolveVideoAudioAnalysisCachePath(request?.sourcePath ?? '')
      const payload = String(request?.payload || '').trim()
      if (!cachePath || !payload) {
        return false
      }
      try {
        await fs.promises.mkdir(path.dirname(cachePath), { recursive: true })
        await fs.promises.writeFile(cachePath, payload, 'utf8')
        return true
      } catch {
        return false
      }
    },
  )

  ipcMain.handle('video:delete-template', (_event, templateId: string) => {
    return deleteVideoTemplate(templateId)
  })

  ipcMain.handle('video:start-manual-export', async (_event, request: ManualVideoExportRequest) => {
    return startManualVideoExport(request)
  })

  ipcMain.handle('video:start-pipeline-export', async (_event, request: VideoPipelineExportRequest) => {
    return startVideoPipelineExport(request)
  })

  ipcMain.handle('video:stop-export', () => {
    return stopVideoExport()
  })

  ipcMain.handle('video-py:start', async () => {
    return openVideoPyWorkspace()
  })

  ipcMain.handle('video-py:stop', () => {
    return closeVideoPyWorkspace()
  })

  ipcMain.handle('video-py:get-state', () => {
    return readVideoPyWorkspaceState()
  })

  ipcMain.handle('video-py:set-host-bounds', (_event, bounds: VideoPreviewHostBounds) => {
    return setVideoPyWorkspaceHostBounds(bounds)
  })

  ipcMain.handle('video-py:send-command', (_event, command: Record<string, unknown>) => {
    const normalized = isRecord(command) ? command : {}
    return sendVideoPyWorkspaceCommand(normalized)
  })

  ipcMain.handle('video-preview:open', async (_event, payload) => {
    const template = isRecord(payload?.template) ? payload.template : {}
    return openVideoPreview({
      template,
      backgroundPath: typeof payload?.backgroundPath === 'string' ? payload.backgroundPath : '',
      logoPath: typeof payload?.logoPath === 'string' ? payload.logoPath : '',
      outputResolution: typeof payload?.outputResolution === 'string' ? payload.outputResolution : '',
    })
  })

  ipcMain.handle('video-preview:close', () => {
    return closeVideoPreview()
  })

  ipcMain.handle('video-preview:set-host-bounds', (_event, bounds: VideoPreviewHostBounds) => {
    return setVideoPreviewHostBounds(bounds)
  })

  ipcMain.handle('video-preview:patch-template', (_event, patch: Record<string, unknown>) => {
    return patchVideoPreviewTemplate(patch)
  })

  ipcMain.handle('video-preview:set-assets', (_event, payload: { backgroundPath?: string; logoPath?: string; audioPath?: string }) => {
    return setVideoPreviewAssets(payload)
  })

  ipcMain.handle('video-export-host:ready', (event) => {
    if (!isVideoExportHostSender(event.sender)) {
      return false
    }
    activeVideoExportHost.ready = true
    activeVideoExport.currentStatus = 'Manual WebGPU export host ready. Loading the live scene…'
    emitVideoWorkspaceEvent('export', 20)
    flushPendingVideoExportHostScene()
    sendCommandToVideoExportHost({ type: 'stop' })
    return true
  })

  ipcMain.handle('video-export-host:set-status', (event, payload: VideoExportHostStatusPayload) => {
    if (!isVideoExportHostSender(event.sender)) {
      return false
    }

    const status = typeof payload?.status === 'string' ? payload.status.trim() : ''
    const message = typeof payload?.message === 'string' ? payload.message.trim() : ''
    activeVideoExportHost.currentStatus = {
      status,
      message: message || undefined,
    }

    switch (status) {
      case 'initializing':
      case 'recovering':
        activeVideoExport.running = true
        activeVideoExport.currentStatus =
          message || 'Manual WebGPU export scene is initializing in the hidden host.'
        break
      case 'running':
        activeVideoExport.currentStatus =
          message || 'Manual WebGPU export host is live. Starting deterministic frame capture…'
        if (
          isManualVideoExportSessionActive() &&
          activeVideoExportHost.currentScene &&
          !activeVideoExportHost.captureProbeRunning
        ) {
          activeVideoExportHost.captureProbeRunning = true
          void runManualVideoExportCapture()
            .catch((error) => {
              closeVideoExportHostWindowSilently()
              resetVideoExportHostSessionState()
              clearManualVideoExportBootstrap(
                error instanceof Error ? error.message : 'Manual WebGPU frame capture failed.',
                {
                  outputDir: activeVideoExport.outputDir,
                },
              )
              emitVideoWorkspaceEvent('export', 20)
            })
            .finally(() => {
              activeVideoExportHost.captureProbeRunning = false
            })
        }
        break
      case 'fallback-active':
        clearManualVideoExportBootstrap(
          message ||
            'Manual WebGPU export host is live, but the fallback scene is active. Export capture stays blocked until the real scene is available.',
        )
        break
      case 'unsupported':
      case 'device-lost':
      case 'error':
        clearManualVideoExportBootstrap(
          message || `Manual WebGPU export host reported ${status || 'an error'}.`,
        )
        break
      default:
        activeVideoExport.currentStatus =
          message || `Manual WebGPU export host status changed${status ? `: ${status}` : '.'}`
        break
    }

    emitVideoWorkspaceEvent('export', 20)
    return true
  })

  ipcMain.handle('video-export-host:set-playback', (event, payload: VideoExportHostPlaybackPayload) => {
    if (!isVideoExportHostSender(event.sender)) {
      return false
    }

    activeVideoExportHost.currentPlayback = {
      isPlaying: Boolean(payload?.isPlaying),
      isReady: Boolean(payload?.isReady),
      isLoading: Boolean(payload?.isLoading),
      currentTimeSec: Number.isFinite(Number(payload?.currentTimeSec)) ? Number(payload.currentTimeSec) : 0,
      durationSec: Number.isFinite(Number(payload?.durationSec)) ? Number(payload.durationSec) : 0,
    }

    if (isManualVideoExportSessionActive()) {
      const playback = activeVideoExportHost.currentPlayback
      activeVideoExport.currentStatus = playback.isLoading
        ? 'Manual WebGPU export audio is loading in the hidden host…'
        : playback.isReady
          ? `Manual WebGPU export host synchronized at ${playback.currentTimeSec.toFixed(2)}s.`
          : activeVideoExport.currentStatus
      emitVideoWorkspaceEvent('export', 20)
    }

    return true
  })

  ipcMain.handle('video-export-host:set-capture-frame', (event, payload: VideoExportHostCaptureFramePayload) => {
    if (!isVideoExportHostSender(event.sender)) {
      return false
    }
    const pendingRequest = pendingVideoExportHostCaptureRequest
    if (!pendingRequest) {
      return false
    }
    const requestId = typeof payload?.requestId === 'string' ? payload.requestId.trim() : ''
    if (!requestId || requestId !== pendingRequest.requestId) {
      return false
    }
    // #region debug-point C:capture-handler
    sendExportSpeedDebug({
      hypothesisId: 'C',
      location: 'main:index.ts:set-capture-frame',
      msg: '[DEBUG] export capture frame handler accepted payload in main',
      data: {
        requestId,
        width: Number(payload?.width ?? 0),
        height: Number(payload?.height ?? 0),
        byteLength:
          payload?.pixelData instanceof Uint8Array
            ? payload.pixelData.byteLength
            : ArrayBuffer.isView(payload?.pixelData)
              ? (payload.pixelData as ArrayBufferView).byteLength
              : 0,
      },
    })
    // #endregion
    pendingVideoExportHostCaptureRequest = null
    clearTimeout(pendingRequest.timeoutId)
    pendingRequest.resolve({
      requestId,
      width: Number.isFinite(Number(payload?.width)) ? Number(payload.width) : 0,
      height: Number.isFinite(Number(payload?.height)) ? Number(payload.height) : 0,
      pixelData: payload?.pixelData instanceof Uint8Array ? payload.pixelData : new Uint8Array(),
    })
    return true
  })

  ipcMain.on('app:get-splash-mode', (event) => {
    event.returnValue = event.sender === splashWindow?.webContents
  })

  ipcMain.on('bootstrap:progress', (_event, payload) => {
    splashWindow?.webContents.send('bootstrap:progress', payload)
  })

  ipcMain.on('bootstrap:done', () => {
    closeSplashAndShowMain()
  })

  ipcMain.on('splash:done', () => {
    closeSplashAndShowMain()
  })

  ipcMain.on('window:minimize', () => {
    mainWindow?.minimize()
  })

  ipcMain.on('window:toggle-maximize', () => {
    if (!mainWindow || mainWindow.isDestroyed()) {
      return
    }

    if (mainWindow.isMaximized()) {
      mainWindow.unmaximize()
      restoreMainWindowToDefaultSize()
      return
    }

    mainWindow.maximize()
  })

  ipcMain.handle('window:is-maximized', () => {
    return mainWindow?.isMaximized() ?? false
  })

  ipcMain.on('window:close', () => {
    mainWindow?.close()
  })
}

function getRendererUrl(): string {
  if (isDev) {
    return devServerUrl
  }
  return `file://${path.join(__dirname, '../renderer/index.html')}`
}

async function createSplashWindow(): Promise<void> {
  splashWindow = new BrowserWindow({
    width: 380,
    height: 176,
    frame: false,
    transparent: false,
    resizable: false,
    maximizable: false,
    fullscreenable: false,
    useContentSize: true,
    center: true,
    skipTaskbar: true,
    backgroundColor: '#0a0e27',
    icon: appIconPath,
    webPreferences: {
      preload: path.join(__dirname, '../preload/index.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  })

  splashWindow.setAlwaysOnTop(true)
  splashCreatedAt = Date.now()

  const splashUrl = withHashRoute(getRendererUrl(), '/startup')
  await splashWindow.loadURL(splashUrl)

  clearSplashFallbackTimer()
  splashFallbackTimer = setTimeout(() => {
    if (!splashWindow || splashWindow.isDestroyed()) {
      return
    }
    closeSplashAndShowMain()
  }, 7000)
}

async function createMainWindow(): Promise<void> {
  mainWindow = new BrowserWindow({
    width: mainWindowDefaultSize.width,
    height: mainWindowDefaultSize.height,
    backgroundColor: '#020617',
    frame: false,
    show: false,
    title: 'CAMXORA',
    autoHideMenuBar: true,
    resizable: true,
    maximizable: true,
    fullscreenable: false,
    center: true,
    icon: appIconPath,
    webPreferences: {
      preload: path.join(__dirname, '../preload/index.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  })

  const mainUrl = withHashRoute(getRendererUrl(), '/startup')

  mainWindow.once('ready-to-show', () => {
    if (shouldShowMainWindow) {
      showMainWindowIfReady()
    }
  })

  mainWindow.on('closed', () => {
    closeVideoPreview()
    closeVideoPyWorkspace()
    mainWindow = null
  })

  await mainWindow.loadURL(mainUrl)

  if (isDev && process.env.CAMXORA_OPEN_DEVTOOLS === '1') {
    mainWindow.webContents.openDevTools({ mode: 'detach' })
  }
}

app.whenReady().then(async () => {
  registerIpcHandlers()
  await createMainWindow()
  await createSplashWindow()

  app.on('activate', async () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      await createMainWindow()
      await createSplashWindow()
    }
  })
})

app.on('window-all-closed', () => {
  if (videoExportHostWindow && !videoExportHostWindow.isDestroyed()) {
    videoExportHostWindow.close()
  }
  if (process.platform !== 'darwin') {
    app.quit()
  }
})
