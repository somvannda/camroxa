import type { DesktopApi, VideoPyWorkspaceState, VideoWorkspaceState } from '@/shared/types/desktop'

const fallbackVideoWorkspaceState: VideoWorkspaceState = {
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
    currentStatus: 'Video bridge is unavailable in browser mode.',
    outputDir: null,
    currentOutputPath: null,
    totalJobs: 0,
    completedJobs: 0,
    lastOutputPath: null,
      lastMergedOutputPath: null,
  },
  ui: {
    previewTitle: 'Preview: unavailable',
    livePreviewOpen: false,
    source: 'fallback',
    notes: ['The Electron video bridge is only available inside the desktop app.'],
  },
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function mergeRecords(base: Record<string, unknown>, patch: Record<string, unknown>): Record<string, unknown> {
  const next: Record<string, unknown> = { ...base }
  Object.entries(patch).forEach(([key, value]) => {
    if (isRecord(value) && isRecord(next[key])) {
      next[key] = mergeRecords(next[key] as Record<string, unknown>, value)
      return
    }
    next[key] = value
  })
  return next
}

const fallbackDesktopApi: DesktopApi = {
  async getAppMeta() {
    return {
      name: 'CAMXORA',
      version: 'dev-browser',
      isDev: true,
      platform: 'web',
    }
  },
  isSplash: false,
  async splashDone() {
    // no-op in browser
  },
  bootstrap: {
    reportProgress: () => undefined,
    done: () => undefined,
    onProgress: () => () => undefined,
  },
  windowControls: {
    minimize: () => undefined,
    toggleMaximize: () => undefined,
    isMaximized: async () => false,
    close: () => undefined,
  },
  secureStorage: {
    async get(key) {
      return window.localStorage.getItem(key)
    },
    async set(key, value) {
      window.localStorage.setItem(key, value)
      return true
    },
    async remove(key) {
      window.localStorage.removeItem(key)
      return true
    },
    async clear() {
      window.localStorage.clear()
      return true
    },
  },
  files: {
    async selectFile() {
      return null
    },
    async selectPath() {
      return null
    },
    async readFileAsBase64() {
      return null
    },
    async saveBase64File() {
      return false
    },
    async ensureDirectory() {
      return false
    },
    async openPath() {
      return false
    },
    async openExternalUrl(targetUrl) {
      try {
        window.open(targetUrl, '_blank', 'noopener,noreferrer')
        return true
      } catch {
        return false
      }
    },
    async listDirectoryEntries() {
      return []
    },
    async listDirectoryImages() {
      return []
    },
    async downloadAndExtractZip() {
      return {
        ok: false,
        installedCount: 0,
        error: 'Sample-pack install is only available inside the desktop app.',
      }
    },
    async downloadMusicTracks(items) {
      return (items?.items ?? []).map((item) => ({
        taskId: item.taskId,
        channel: item.channel,
        ok: false,
        outputDir: item.outputDir ?? null,
        targetPath: item.targetPath ?? null,
        skippedExisting: false,
        error: 'Music download is only available inside the desktop app.',
      }))
    },
  },
  effectPacks: {
    async listCatalog() {
      return { items: [] }
    },
    async installFromUrl() {
      return {
        ok: false,
        item: null,
        replacedVersion: null,
        error: 'Effect-pack install is only available inside the desktop app.',
      }
    },
    async installFromFile() {
      return {
        ok: false,
        item: null,
        replacedVersion: null,
        error: 'Effect-pack install is only available inside the desktop app.',
      }
    },
    async setEnabled() {
      return {
        ok: false,
        item: null,
        error: 'Effect-pack management is only available inside the desktop app.',
      }
    },
    async activateVersion() {
      return {
        ok: false,
        item: null,
        error: 'Effect-pack management is only available inside the desktop app.',
      }
    },
    async removeVersion() {
      return {
        ok: false,
        removed: false,
        error: 'Effect-pack management is only available inside the desktop app.',
      }
    },
  },
  video: {
    async getWorkspaceState() {
      return fallbackVideoWorkspaceState
    },
    async setTemplate() {
      return fallbackVideoWorkspaceState
    },
    async deleteTemplate() {
      return fallbackVideoWorkspaceState
    },
    async setOutputResolution(resolution) {
      return {
        ...fallbackVideoWorkspaceState,
        outputResolution: resolution,
      }
    },
    async setBackgroundPath(backgroundPath) {
      return {
        ...fallbackVideoWorkspaceState,
        backgroundPath,
      }
    },
    async setLogoPath(logoPath) {
      return {
        ...fallbackVideoWorkspaceState,
        logoPath,
      }
    },
    async setMp3Path(mp3Path) {
      return {
        ...fallbackVideoWorkspaceState,
        selectedMp3Path: mp3Path,
        mp3List: mp3Path
          ? [
              {
                name: mp3Path.split(/[\\/]/).pop() || mp3Path,
                path: mp3Path,
              },
            ]
          : [],
      }
    },
    async patchTemplate(patch) {
      return {
        ...fallbackVideoWorkspaceState,
        template: mergeRecords(
          isRecord(fallbackVideoWorkspaceState.template) ? fallbackVideoWorkspaceState.template : {},
          patch,
        ),
      }
    },
    async getAudioAnalysisCache() {
      return null
    },
    async setAudioAnalysisCache() {
      return false
    },
    async startManualExport() {
      return {
        ...fallbackVideoWorkspaceState,
        export: {
          ...fallbackVideoWorkspaceState.export,
          currentStatus: 'Manual video export is only available inside the desktop app.',
        },
      }
    },
    async startPipelineExport() {
      return {
        ...fallbackVideoWorkspaceState,
        export: {
          ...fallbackVideoWorkspaceState.export,
          currentStatus: 'Video export is only available inside the desktop app.',
        },
      }
    },
    async stopExport() {
      return fallbackVideoWorkspaceState
    },
    onWorkspaceEvent: () => () => undefined,
  },
  videoPreview: {
    async open() {
      return false
    },
    async close() {
      return false
    },
    async setHostBounds() {
      return false
    },
    async patchTemplate() {
      return false
    },
    async setAssets() {
      return false
    },
    onEvent: () => () => undefined,
  },
  videoExportHost: {
    async ready() {
      return false
    },
    async setStatus() {
      return false
    },
    async setPlayback() {
      return false
    },
    async setCaptureFrame() {
      return false
    },
    onScene: () => () => undefined,
    onCommand: () => () => undefined,
  },
  videoPy: {
    async start(): Promise<VideoPyWorkspaceState> {
      return { running: false, embedded: false, pid: null }
    },
    async stop(): Promise<VideoPyWorkspaceState> {
      return { running: false, embedded: false, pid: null }
    },
    async getState(): Promise<VideoPyWorkspaceState> {
      return { running: false, embedded: false, pid: null }
    },
    async setHostBounds() {
      return false
    },
    async sendCommand() {
      return false
    },
    onEvent: () => () => undefined,
  },
}

export function getDesktopApi(): DesktopApi {
  return window.camxoraDesktop ?? fallbackDesktopApi
}
