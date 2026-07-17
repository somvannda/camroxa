import { contextBridge, ipcRenderer } from 'electron'

import type {
  DirectoryEntry,
  DownloadAndExtractZipResult,
  EffectPackActivateResult,
  EffectPackCatalogResponse,
  EffectPackInstallResult,
  EffectPackRemoveResult,
  EffectPackToggleResult,
  MusicTrackDownloadRequest,
  MusicTrackDownloadResult,
  VideoAudioAnalysisCacheRequest,
  VideoAudioAnalysisCacheWriteRequest,
  VideoExportHostCommandPayload,
  VideoExportHostPlaybackPayload,
  VideoExportHostStatusPayload,
  VideoPyWorkspaceEventPayload,
  VideoPyWorkspaceState,
  StartManualVideoExportRequest,
  StartVideoPipelineExportRequest,
  VideoPreviewEventPayload,
  VideoPreviewHostBounds,
  VideoSerializableRenderSceneRequest,
  VideoWorkspaceEventPayload,
  VideoWorkspaceState,
} from '../renderer/src/shared/types/desktop'

export type AppMeta = {
  name: string
  version: string
  isDev: boolean
  platform: NodeJS.Platform
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
    listDirectoryEntries: (options: { directoryPath: string; maxResults?: number }) => Promise<DirectoryEntry[]>
    listDirectoryImages: (options: { directoryPath: string; maxResults?: number }) => Promise<string[]>
    downloadAndExtractZip: (options: { url: string; destinationDir: string }) => Promise<DownloadAndExtractZipResult>
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

let isSplash = false
try {
  isSplash = Boolean(ipcRenderer.sendSync('app:get-splash-mode'))
} catch {
  isSplash = false
}

const desktopApi: DesktopApi = {
  getAppMeta: () => ipcRenderer.invoke('app:get-meta'),
  isSplash,
  splashDone: () => {
    ipcRenderer.send('splash:done')
    return Promise.resolve()
  },
  bootstrap: {
    reportProgress: (payload) => ipcRenderer.send('bootstrap:progress', payload),
    done: () => ipcRenderer.send('bootstrap:done'),
    onProgress: (handler) => {
      const wrapped = (_event: unknown, payload: { label: string; detail: string; progress: number }) =>
        handler(payload)
      ipcRenderer.on('bootstrap:progress', wrapped)
      return () => ipcRenderer.off('bootstrap:progress', wrapped)
    },
  },
  windowControls: {
    minimize: () => ipcRenderer.send('window:minimize'),
    toggleMaximize: () => ipcRenderer.send('window:toggle-maximize'),
    isMaximized: () => ipcRenderer.invoke('window:is-maximized'),
    close: () => ipcRenderer.send('window:close'),
  },
  secureStorage: {
    get: (key) => ipcRenderer.invoke('secure-storage:get', key),
    set: (key, value) => ipcRenderer.invoke('secure-storage:set', key, value),
    remove: (key) => ipcRenderer.invoke('secure-storage:remove', key),
    clear: () => ipcRenderer.invoke('secure-storage:clear'),
  },
  files: {
    selectFile: (options) => ipcRenderer.invoke('files:select-file', options),
    selectPath: (options) => ipcRenderer.invoke('files:select-path', options),
    readFileAsBase64: (targetPath) => ipcRenderer.invoke('files:read-file-as-base64', targetPath),
    saveBase64File: (options) => ipcRenderer.invoke('files:save-base64-file', options),
    ensureDirectory: (targetPath) => ipcRenderer.invoke('files:ensure-directory', targetPath),
    openPath: (targetPath) => ipcRenderer.invoke('files:open-path', targetPath),
    openExternalUrl: (targetUrl) => ipcRenderer.invoke('files:open-external-url', targetUrl),
    listDirectoryEntries: (options: { directoryPath: string; maxResults?: number }) =>
      ipcRenderer.invoke('files:list-directory-entries', options),
    listDirectoryImages: (options: { directoryPath: string; maxResults?: number }) =>
      ipcRenderer.invoke('files:list-directory-images', options),
    downloadAndExtractZip: (options) => ipcRenderer.invoke('files:download-and-extract-zip', options),
    downloadMusicTracks: (options) => ipcRenderer.invoke('files:download-music-tracks', options),
  },
  effectPacks: {
    listCatalog: () => ipcRenderer.invoke('effect-packs:list-catalog'),
    installFromUrl: (options) => ipcRenderer.invoke('effect-packs:install-from-url', options),
    installFromFile: (options) => ipcRenderer.invoke('effect-packs:install-from-file', options),
    setEnabled: (options) => ipcRenderer.invoke('effect-packs:set-enabled', options),
    activateVersion: (options) => ipcRenderer.invoke('effect-packs:activate-version', options),
    removeVersion: (options) => ipcRenderer.invoke('effect-packs:remove-version', options),
  },
  video: {
    getWorkspaceState: () => ipcRenderer.invoke('video:get-workspace-state'),
    setTemplate: (templateId) => ipcRenderer.invoke('video:set-template', templateId),
    deleteTemplate: (templateId) => ipcRenderer.invoke('video:delete-template', templateId),
    setOutputResolution: (resolution) => ipcRenderer.invoke('video:set-output-resolution', resolution),
    setBackgroundPath: (backgroundPath) => ipcRenderer.invoke('video:set-background-path', backgroundPath),
    setLogoPath: (logoPath) => ipcRenderer.invoke('video:set-logo-path', logoPath),
    setMp3Path: (mp3Path) => ipcRenderer.invoke('video:set-mp3-path', mp3Path),
    patchTemplate: (patch) => ipcRenderer.invoke('video:patch-template', patch),
    getAudioAnalysisCache: (request) => ipcRenderer.invoke('video:get-audio-analysis-cache', request),
    setAudioAnalysisCache: (request) => ipcRenderer.invoke('video:set-audio-analysis-cache', request),
    startManualExport: (request) => ipcRenderer.invoke('video:start-manual-export', request),
    startPipelineExport: (request) => ipcRenderer.invoke('video:start-pipeline-export', request),
    stopExport: () => ipcRenderer.invoke('video:stop-export'),
    onWorkspaceEvent: (handler) => {
      const wrapped = (_event: unknown, payload: VideoWorkspaceEventPayload) => handler(payload)
      ipcRenderer.on('video:workspace-event', wrapped)
      return () => ipcRenderer.off('video:workspace-event', wrapped)
    },
  },
  videoPreview: {
    open: (payload) => ipcRenderer.invoke('video-preview:open', payload),
    close: () => ipcRenderer.invoke('video-preview:close'),
    setHostBounds: (bounds) => ipcRenderer.invoke('video-preview:set-host-bounds', bounds),
    patchTemplate: (patch) => ipcRenderer.invoke('video-preview:patch-template', patch),
    setAssets: (payload) => ipcRenderer.invoke('video-preview:set-assets', payload),
    onEvent: (handler) => {
      const wrapped = (_event: unknown, payload: VideoPreviewEventPayload) => handler(payload)
      ipcRenderer.on('video-preview:event', wrapped)
      return () => ipcRenderer.off('video-preview:event', wrapped)
    },
  },
  videoExportHost: {
    ready: () => ipcRenderer.invoke('video-export-host:ready'),
    setStatus: (payload) => ipcRenderer.invoke('video-export-host:set-status', payload),
    setPlayback: (payload) => ipcRenderer.invoke('video-export-host:set-playback', payload),
    setCaptureFrame: (payload) => ipcRenderer.invoke('video-export-host:set-capture-frame', payload),
    onScene: (handler) => {
      const wrapped = (_event: unknown, payload: VideoSerializableRenderSceneRequest) => handler(payload)
      ipcRenderer.on('video-export-host:scene', wrapped)
      return () => ipcRenderer.off('video-export-host:scene', wrapped)
    },
    onCommand: (handler) => {
      const wrapped = (_event: unknown, payload: VideoExportHostCommandPayload) => handler(payload)
      ipcRenderer.on('video-export-host:command', wrapped)
      return () => ipcRenderer.off('video-export-host:command', wrapped)
    },
  },
  videoPy: {
    start: () => ipcRenderer.invoke('video-py:start'),
    stop: () => ipcRenderer.invoke('video-py:stop'),
    getState: () => ipcRenderer.invoke('video-py:get-state'),
    setHostBounds: (bounds) => ipcRenderer.invoke('video-py:set-host-bounds', bounds),
    sendCommand: (command) => ipcRenderer.invoke('video-py:send-command', command),
    onEvent: (handler) => {
      const wrapped = (_event: unknown, payload: VideoPyWorkspaceEventPayload) => handler(payload)
      ipcRenderer.on('video-py:event', wrapped)
      return () => ipcRenderer.off('video-py:event', wrapped)
    },
  },
}

contextBridge.exposeInMainWorld('camxoraDesktop', desktopApi)
