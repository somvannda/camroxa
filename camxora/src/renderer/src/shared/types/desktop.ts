export type AppMeta = {
  name: string
  version: string
  isDev: boolean
  platform: string
}

export type VideoTemplateSummary = {
  id: string
  name: string
  kind: string | null
  updatedAt: string | null
}

export type VideoPlaybackState = {
  isPlaying: boolean
  isReady: boolean
  isLoading: boolean
  currentTimeSec: number
  durationSec: number
}

export type VideoExportState = {
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

export type VideoExportMode = 'manual' | 'pipeline'

export type VideoRenderOutputSettings = {
  resolution: string
  width: number
  height: number
  fps: number
}

export type VideoResolvedRenderAssets = {
  backgroundPath: string | null
  logoPath: string | null
  audioPath: string | null
  runDir: string | null
}

export type VideoSerializableRenderSceneContext = {
  templateId: string | null
  branch: 'long' | 'reel' | null
  batchId: string | null
  role: string | null
  draftSource: 'live' | 'saved'
}

export type VideoSerializableRenderSceneRequest = {
  mode: VideoExportMode
  template: Record<string, unknown>
  draft: Record<string, unknown>
  assets: VideoResolvedRenderAssets
  output: VideoRenderOutputSettings
  context: VideoSerializableRenderSceneContext
}

export type StartManualVideoExportRequest = {
  scene: VideoSerializableRenderSceneRequest
}

export type VideoExportHostStatusPayload = {
  status: string
  message?: string
}

export type VideoExportHostCommandPayload =
  | { type: 'play' }
  | { type: 'pause' }
  | { type: 'stop' }
  | { type: 'seek'; timeSec: number }
  | { type: 'capture-frame'; requestId: string; timeSec: number }

export type VideoExportHostPlaybackPayload = VideoPlaybackState

export type VideoExportHostCaptureFramePayload = {
  requestId: string
  width: number
  height: number
  pixelData: Uint8Array
}

export type StartVideoPipelineExportRequest = {
  runDir: string
  backgroundPath: string
  branch: 'long' | 'reel'
  batchId: string
  role: string
  settings?: Record<string, unknown> | null
  autoMerge?: boolean | null
}

export type VideoPreviewHostBounds = {
  x: number
  y: number
  width: number
  height: number
  dpr: number
}

export type VideoPreviewEventPayload = {
  status: string
  message?: string
  preview?: {
    pid?: number
    hwnd?: number
    platform?: string
  }
}

export type VideoWorkspaceEventPayload = {
  reason: 'template' | 'output' | 'export'
  timestamp: number
}

export type VideoAudioAnalysisCacheRequest = {
  sourcePath: string
}

export type VideoAudioAnalysisCacheWriteRequest = {
  sourcePath: string
  payload: string
}

export type VideoWorkspaceState = {
  template: Record<string, unknown>
  templateId: string | null
  templateName: string
  templates: VideoTemplateSummary[]
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
  playback: VideoPlaybackState
  export: VideoExportState
  ui: {
    previewTitle: string
    livePreviewOpen: boolean
    source: 'python-local' | 'fallback'
    notes: string[]
  }
}

export type DownloadAndExtractZipResult = {
  ok: boolean
  installedCount: number
  error?: string
}

export type EffectPackDomain = 'spectrum' | 'background' | 'logo' | 'particles'

export type EffectPackCatalogStatus =
  | 'ready'
  | 'disabled'
  | 'incompatible'
  | 'broken'
  | 'missing'
  | 'available'

export type EffectPackCatalogItem = {
  packId: string
  version: string
  domain: EffectPackDomain
  name: string
  vendor: string
  description: string
  tags: string[]
  appVersionRange: string
  domainContractVersion: number
  manifestVersion: number
  enabled: boolean
  active: boolean
  status: EffectPackCatalogStatus
  installedAt: string
  sourceType: 'url' | 'file'
  sourceValue: string
  directoryPath: string
  preview: {
    title: string
    summary: string
    accentColor: string
  } | null
  templatePatch: Record<string, unknown>
  issues: string[]
}

export type EffectPackCatalogResponse = {
  items: EffectPackCatalogItem[]
}

export type EffectPackInstallResult = {
  ok: boolean
  item: EffectPackCatalogItem | null
  replacedVersion: string | null
  error?: string
}

export type EffectPackToggleResult = {
  ok: boolean
  item: EffectPackCatalogItem | null
  error?: string
}

export type EffectPackActivateResult = {
  ok: boolean
  item: EffectPackCatalogItem | null
  error?: string
}

export type EffectPackRemoveResult = {
  ok: boolean
  removed: boolean
  error?: string
}

export type MusicTrackDownloadRequest = {
  taskId: string
  channel: 'primary' | 'secondary'
  url: string
  outputDir: string
  targetPath: string
}

export type MusicTrackDownloadResult = {
  taskId: string
  channel: 'primary' | 'secondary'
  ok: boolean
  outputDir: string | null
  targetPath: string | null
  skippedExisting: boolean
  error?: string
}

export type VideoPyWorkspaceEventPayload = {
  status: string
  message?: string
  preview?: {
    pid?: number
    hwnd?: number
    platform?: string
  }
}

export type VideoPyWorkspaceState = {
  running: boolean
  embedded: boolean
  pid: number | null
}

export type DirectoryEntry = {
  name: string
  isDirectory: boolean
}

export type DesktopApi = {
  getAppMeta: () => Promise<AppMeta>
  splashDone: () => Promise<void>
  isSplash: boolean
  bootstrap: {
    reportProgress: (payload: { label: string; detail: string; progress: number }) => void
    done: () => void
    onProgress: (
      handler: (payload: { label: string; detail: string; progress: number }) => void,
    ) => () => void
  }
  windowControls: {
    minimize: () => void
    toggleMaximize: () => void
    isMaximized: () => Promise<boolean>
    close: () => void
  }
  secureStorage: {
    get: (key: string) => Promise<string | null>
    set: (key: string, value: string) => Promise<boolean>
    remove: (key: string) => Promise<boolean>
    clear: () => Promise<boolean>
  }
  files: {
    selectFile: (options?: {
      title?: string
      filters?: Array<{ name: string; extensions: string[] }>
    }) => Promise<string | null>
    selectPath: (options?: {
      title?: string
      kind?: 'file' | 'directory'
      filters?: Array<{ name: string; extensions: string[] }>
    }) => Promise<string | null>
    readFileAsBase64: (targetPath: string) => Promise<string | null>
    saveBase64File: (options: {
      title?: string
      defaultPath?: string
      filters?: Array<{ name: string; extensions: string[] }>
      base64: string
    }) => Promise<boolean>
    ensureDirectory: (targetPath: string) => Promise<boolean>
    openPath: (targetPath: string) => Promise<boolean>
    openExternalUrl: (targetUrl: string) => Promise<boolean>
    listDirectoryEntries: (options: {
      directoryPath: string
      maxResults?: number
    }) => Promise<DirectoryEntry[]>
    listDirectoryImages: (options: {
      directoryPath: string
      maxResults?: number
    }) => Promise<string[]>
    downloadAndExtractZip: (options: {
      url: string
      destinationDir: string
    }) => Promise<DownloadAndExtractZipResult>
    downloadMusicTracks: (options: {
      items: MusicTrackDownloadRequest[]
      retryCount?: number
    }) => Promise<MusicTrackDownloadResult[]>
  }
  effectPacks: {
    listCatalog: () => Promise<EffectPackCatalogResponse>
    installFromUrl: (options: { url: string }) => Promise<EffectPackInstallResult>
    installFromFile: (options: { zipPath: string }) => Promise<EffectPackInstallResult>
    setEnabled: (options: { packId: string; enabled: boolean }) => Promise<EffectPackToggleResult>
    activateVersion: (options: { packId: string; version: string }) => Promise<EffectPackActivateResult>
    removeVersion: (options: { packId: string; version: string }) => Promise<EffectPackRemoveResult>
  }
  video: {
    getWorkspaceState: () => Promise<VideoWorkspaceState>
    setTemplate: (templateId: string) => Promise<VideoWorkspaceState>
    deleteTemplate: (templateId: string) => Promise<VideoWorkspaceState>
    setOutputResolution: (resolution: string) => Promise<VideoWorkspaceState>
    setBackgroundPath: (backgroundPath: string) => Promise<VideoWorkspaceState>
    setLogoPath: (logoPath: string) => Promise<VideoWorkspaceState>
    setMp3Path: (mp3Path: string) => Promise<VideoWorkspaceState>
    patchTemplate: (patch: Record<string, unknown>) => Promise<VideoWorkspaceState>
    getAudioAnalysisCache: (request: VideoAudioAnalysisCacheRequest) => Promise<string | null>
    setAudioAnalysisCache: (request: VideoAudioAnalysisCacheWriteRequest) => Promise<boolean>
    startManualExport: (request: StartManualVideoExportRequest) => Promise<VideoWorkspaceState>
    startPipelineExport: (request: StartVideoPipelineExportRequest) => Promise<VideoWorkspaceState>
    stopExport: () => Promise<VideoWorkspaceState>
    onWorkspaceEvent: (handler: (payload: VideoWorkspaceEventPayload) => void) => () => void
  }
  videoPreview: {
    open: (payload: { template: Record<string, unknown>; backgroundPath?: string; logoPath?: string; outputResolution?: string }) => Promise<boolean>
    close: () => Promise<boolean>
    setHostBounds: (bounds: VideoPreviewHostBounds) => Promise<boolean>
    patchTemplate: (patch: Record<string, unknown>) => Promise<boolean>
    setAssets: (payload: { backgroundPath?: string; logoPath?: string; audioPath?: string }) => Promise<boolean>
    onEvent: (handler: (payload: VideoPreviewEventPayload) => void) => () => void
  }
  videoExportHost: {
    ready: () => Promise<boolean>
    setStatus: (payload: VideoExportHostStatusPayload) => Promise<boolean>
    setPlayback: (payload: VideoExportHostPlaybackPayload) => Promise<boolean>
    setCaptureFrame: (payload: VideoExportHostCaptureFramePayload) => Promise<boolean>
    onScene: (handler: (payload: VideoSerializableRenderSceneRequest) => void) => () => void
    onCommand: (handler: (payload: VideoExportHostCommandPayload) => void) => () => void
  }
  videoPy: {
    start: () => Promise<VideoPyWorkspaceState>
    stop: () => Promise<VideoPyWorkspaceState>
    getState: () => Promise<VideoPyWorkspaceState>
    setHostBounds: (bounds: VideoPreviewHostBounds) => Promise<boolean>
    sendCommand: (command: Record<string, unknown>) => Promise<boolean>
    onEvent: (handler: (payload: VideoPyWorkspaceEventPayload) => void) => () => void
  }
}
