import {
  createAudioSpectrumLogMapping,
  type AudioSpectrumEnvelope,
  type AudioSpectrumLogMapping,
} from '@/features/video/preview/audioSpectrumAnalysis'
import {
  buildPreviewAudioReactiveFeatureTimelineFromAudioBuffer,
  type PreviewAudioReactiveFeatureTimeline,
} from '@/features/video/preview/audioReactiveTimeline'
import {
  loadCachedPreviewAudioReactiveTimeline,
  storeCachedPreviewAudioReactiveTimeline,
} from '@/features/video/preview/previewAudioAnalysisCache'
import {
  buildPreviewPlaybackState,
  createIdlePreviewPlaybackState,
  type PreviewPlaybackCommand,
} from '@/features/video/preview/transportClock'
import { createVideoDebugSender } from '@/features/video/videoDiagnostics'
import { getDesktopApi } from '@/shared/api/desktop'
import type { VideoWorkspaceState } from '@/shared/types/desktop'

export type AudioAnalysisRuntime = {
  analyser: AnalyserNode | null
  frequencyData: Uint8Array | null
  audioContext: AudioContext | null
  audioElement: HTMLAudioElement | null
  featureTimeline: PreviewAudioReactiveFeatureTimeline | null
  gainNode: GainNode | null
  spectrumMapping: AudioSpectrumLogMapping | null
  envelope: AudioSpectrumEnvelope
}

type CreatePreviewAudioFeatureBusOptions = {
  selectedMp3Path: string
  audioMotionSmoothing: number
  previewVolume: number
  onPlaybackStateChange: (state: VideoWorkspaceState['playback']) => void
  onPlaybackError: (message: string) => void
}

type PreviewAudioFeatureBusSession = {
  runtime: AudioAnalysisRuntime
  teardown: () => void
}

const previewAudioSourceCache = new Map<string, Promise<string>>()
const previewAudioArrayBufferCache = new Map<string, Promise<ArrayBuffer | null>>()
const previewAudioReactiveTimelineCache = new Map<string, Promise<PreviewAudioReactiveFeatureTimeline | null>>()

const sendVideoPageLagDebug = createVideoDebugSender({
  sessionId: 'video-page-lag',
  runId: 'pre-fix',
})

function toFileUrl(targetPath: string): string {
  const normalized = targetPath.trim().replace(/\\/g, '/')
  if (!normalized) {
    return ''
  }
  if (/^[a-z]+:\/\//i.test(normalized)) {
    return normalized
  }
  if (/^[a-z]:\//i.test(normalized)) {
    return encodeURI(`file:///${normalized}`)
  }
  return encodeURI(`file://${normalized.startsWith('/') ? '' : '/'}${normalized}`)
}

function getAudioMimeType(targetPath: string): string {
  const normalized = targetPath.trim().toLowerCase()
  if (normalized.endsWith('.wav')) {
    return 'audio/wav'
  }
  if (normalized.endsWith('.ogg')) {
    return 'audio/ogg'
  }
  if (normalized.endsWith('.m4a')) {
    return 'audio/mp4'
  }
  return 'audio/mpeg'
}

export function createEmptyAudioSpectrumEnvelope(): AudioSpectrumEnvelope {
  return {
    bassFast: 0,
    bassSlow: 0,
    kick: 0,
    drop: 0,
    level: 0,
    peakHoldBands: null,
    energyBands: null,
    slowBands: null,
    floorBands: null,
    transientBands: null,
    onsetBands: null,
    previousBands: null,
  }
}

export function createEmptyAudioAnalysisRuntime(): AudioAnalysisRuntime {
  return {
    analyser: null,
    frequencyData: null,
    audioContext: null,
    audioElement: null,
    featureTimeline: null,
    gainNode: null,
    spectrumMapping: null,
    envelope: createEmptyAudioSpectrumEnvelope(),
  }
}

export function disposePreviewAudioRuntime(runtime: AudioAnalysisRuntime): void {
  runtime.analyser?.disconnect()
  runtime.gainNode?.disconnect()
  runtime.audioElement?.pause()
  if (runtime.audioElement) {
    runtime.audioElement.src = ''
  }
  void runtime.audioContext?.close()
}

export async function resolvePreviewAudioSource(targetPath: string): Promise<string> {
  const normalized = targetPath.trim()
  if (!normalized) {
    return ''
  }
  if (/^https?:\/\//i.test(normalized)) {
    return normalized
  }
  const cached = previewAudioSourceCache.get(normalized)
  if (cached) {
    return cached
  }

  const sourcePromise = (async () => {
    try {
      const readStart = performance.now()
      const base64 = await getDesktopApi().files.readFileAsBase64(normalized)
      // #region debug-point A:audio-source-base64
      sendVideoPageLagDebug({
        hypothesisId: 'A',
        location: 'audioFeatureBus:resolvePreviewAudioSource',
        msg: '[DEBUG] preview audio source base64 read completed',
        data: {
          targetPath: normalized,
          elapsedMs: Number((performance.now() - readStart).toFixed(2)),
          base64Length: base64?.length ?? 0,
        },
      })
      // #endregion
      if (base64) {
        return `data:${getAudioMimeType(normalized)};base64,${base64}`
      }
    } catch {
      // Fall back to a file URL only if desktop decoding is unavailable.
    }

    return toFileUrl(normalized)
  })()

  previewAudioSourceCache.set(normalized, sourcePromise)
  return sourcePromise
}

function base64ToArrayBuffer(base64: string): ArrayBuffer {
  const binary = window.atob(base64)
  const bytes = new Uint8Array(binary.length)
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index)
  }
  return bytes.buffer
}

async function resolvePreviewAudioArrayBuffer(
  targetPath: string,
  audioSource: string,
): Promise<ArrayBuffer | null> {
  const normalized = targetPath.trim()
  const cacheKey = normalized || audioSource.trim()
  const cached = previewAudioArrayBufferCache.get(cacheKey)
  if (cached) {
    return cached
  }

  const arrayBufferPromise = (async () => {
  if (normalized) {
    try {
      const readStart = performance.now()
      const base64 = await getDesktopApi().files.readFileAsBase64(normalized)
      // #region debug-point A:audio-array-buffer-base64
      sendVideoPageLagDebug({
        hypothesisId: 'A',
        location: 'audioFeatureBus:resolvePreviewAudioArrayBuffer',
        msg: '[DEBUG] preview audio array buffer base64 read completed',
        data: {
          targetPath: normalized,
          elapsedMs: Number((performance.now() - readStart).toFixed(2)),
          base64Length: base64?.length ?? 0,
        },
      })
      // #endregion
      if (base64) {
        return base64ToArrayBuffer(base64)
      }
    } catch {
      // Fall through to a generic fetch when desktop decoding is unavailable.
    }
  }

  if (!audioSource) {
    return null
  }

  try {
    const fetchStart = performance.now()
    const response = await fetch(audioSource)
    if (!response.ok) {
      return null
    }
    const buffer = await response.arrayBuffer()
    // #region debug-point A:audio-array-buffer-fetch
    sendVideoPageLagDebug({
      hypothesisId: 'A',
      location: 'audioFeatureBus:resolvePreviewAudioArrayBuffer:fetch',
      msg: '[DEBUG] preview audio array buffer fetch completed',
      data: {
        targetPath: normalized,
        elapsedMs: Number((performance.now() - fetchStart).toFixed(2)),
        byteLength: buffer.byteLength,
      },
    })
    // #endregion
    return buffer
  } catch {
    return null
  }
  })()

  previewAudioArrayBufferCache.set(cacheKey, arrayBufferPromise)
  return arrayBufferPromise
}

async function buildPreviewAudioReactiveTimeline(
  audioContext: AudioContext,
  targetPath: string,
  audioSource: string,
): Promise<PreviewAudioReactiveFeatureTimeline | null> {
  const cacheKey = targetPath.trim() || audioSource.trim()
  const cached = previewAudioReactiveTimelineCache.get(cacheKey)
  if (cached) {
    return cached
  }

  const timelinePromise = (async () => {
    const persistentTimeline = await loadCachedPreviewAudioReactiveTimeline(targetPath)
    if (persistentTimeline) {
      // #region debug-point A:audio-timeline-persistent-cache-hit
      sendVideoPageLagDebug({
        hypothesisId: 'A',
        location: 'audioFeatureBus:buildPreviewAudioReactiveTimeline:persistent-cache',
        msg: '[DEBUG] preview audio reactive timeline restored from persistent cache',
        data: {
          targetPath,
          frameCount: persistentTimeline.frames.length,
          durationSec: Number(persistentTimeline.durationSec.toFixed(3)),
        },
      })
      // #endregion
      return persistentTimeline
    }

    const sourceBuffer = await resolvePreviewAudioArrayBuffer(targetPath, audioSource)
    if (!sourceBuffer) {
      return null
    }

    try {
      const decodedBuffer = await audioContext.decodeAudioData(sourceBuffer.slice(0))
      const timeline = buildPreviewAudioReactiveFeatureTimelineFromAudioBuffer(decodedBuffer)
      void storeCachedPreviewAudioReactiveTimeline(targetPath, timeline)
      return timeline
    } catch {
      return null
    }
  })()

  previewAudioReactiveTimelineCache.set(cacheKey, timelinePromise)
  return timelinePromise
}

export async function createPreviewAudioFeatureBus({
  selectedMp3Path,
  audioMotionSmoothing,
  previewVolume,
  onPlaybackStateChange,
  onPlaybackError,
}: CreatePreviewAudioFeatureBusOptions): Promise<PreviewAudioFeatureBusSession | null> {
  const bootstrapStart = performance.now()
  if (!selectedMp3Path.trim()) {
    return null
  }
  if (typeof window === 'undefined' || /jsdom/i.test(navigator.userAgent)) {
    return null
  }
  if (typeof window.AudioContext === 'undefined') {
    return null
  }

  const audioSource = await resolvePreviewAudioSource(selectedMp3Path)
  // #region debug-point A:audio-bootstrap-source
  sendVideoPageLagDebug({
    hypothesisId: 'A',
    location: 'audioFeatureBus:createPreviewAudioFeatureBus:source',
    msg: '[DEBUG] preview audio bootstrap source resolved',
    data: {
      selectedMp3Path,
      elapsedMs: Number((performance.now() - bootstrapStart).toFixed(2)),
      sourceKind: audioSource.startsWith('data:') ? 'data-url' : audioSource.startsWith('file:') ? 'file-url' : 'remote',
      sourceLength: audioSource.length,
    },
  })
  // #endregion
  if (!audioSource) {
    return null
  }

  const audioContext = new window.AudioContext()
  const analyser = audioContext.createAnalyser()
  analyser.fftSize = 1024
  analyser.smoothingTimeConstant = clamp(audioMotionSmoothing, 0, 0.97)

  const gainNode = audioContext.createGain()
  gainNode.gain.value = clamp(previewVolume, 0, 2)

  const audioElement = new Audio()
  audioElement.loop = true
  audioElement.preload = 'auto'
  if (/^https?:\/\//i.test(audioSource)) {
    audioElement.crossOrigin = 'anonymous'
  }
  audioElement.src = audioSource

  const sourceNode = audioContext.createMediaElementSource(audioElement)
  sourceNode.connect(analyser)
  analyser.connect(gainNode)
  gainNode.connect(audioContext.destination)

  const runtime: AudioAnalysisRuntime = {
    analyser,
    frequencyData: new Uint8Array(analyser.frequencyBinCount),
    audioContext,
    audioElement,
    featureTimeline: null,
    gainNode,
    spectrumMapping: createAudioSpectrumLogMapping(analyser.frequencyBinCount),
    envelope: createEmptyAudioSpectrumEnvelope(),
  }

  onPlaybackStateChange(createIdlePreviewPlaybackState({ isLoading: true }))

  const handleMediaEvent = () => {
    onPlaybackStateChange(buildPreviewPlaybackState(audioElement))
  }

  const handleMediaError = () => {
    onPlaybackStateChange(createIdlePreviewPlaybackState())
    onPlaybackError('Preview audio failed to load. Please reselect the MP3 and try again.')
  }

  audioElement.addEventListener('loadedmetadata', handleMediaEvent)
  audioElement.addEventListener('canplay', handleMediaEvent)
  audioElement.addEventListener('waiting', handleMediaEvent)
  audioElement.addEventListener('error', handleMediaError)
  audioElement.addEventListener('play', handleMediaEvent)
  audioElement.addEventListener('playing', handleMediaEvent)
  audioElement.addEventListener('pause', handleMediaEvent)
  audioElement.addEventListener('ended', handleMediaEvent)
  audioElement.addEventListener('timeupdate', handleMediaEvent)
  audioElement.addEventListener('seeking', handleMediaEvent)
  audioElement.addEventListener('seeked', handleMediaEvent)
  audioElement.load()

  void (async () => {
    const timelineStart = performance.now()
    const timeline = await buildPreviewAudioReactiveTimeline(audioContext, selectedMp3Path, audioSource)
    runtime.featureTimeline = timeline
    // #region debug-point A:audio-bootstrap-timeline
    sendVideoPageLagDebug({
      hypothesisId: 'A',
      location: 'audioFeatureBus:createPreviewAudioFeatureBus:timeline',
      msg: '[DEBUG] preview audio reactive timeline completed',
      data: {
        selectedMp3Path,
        elapsedMs: Number((performance.now() - timelineStart).toFixed(2)),
        totalElapsedMs: Number((performance.now() - bootstrapStart).toFixed(2)),
        timelineReady: Boolean(timeline),
        frameCount: timeline?.frames.length ?? 0,
      },
    })
    // #endregion
  })()

  // #region debug-point A:audio-bootstrap-ready
  sendVideoPageLagDebug({
    hypothesisId: 'A',
    location: 'audioFeatureBus:createPreviewAudioFeatureBus:ready',
    msg: '[DEBUG] preview audio feature bus created',
    data: {
      selectedMp3Path,
      elapsedMs: Number((performance.now() - bootstrapStart).toFixed(2)),
      fftSize: analyser.fftSize,
      frequencyBinCount: analyser.frequencyBinCount,
    },
  })
  // #endregion

  return {
    runtime,
    teardown: () => {
      audioElement.removeEventListener('loadedmetadata', handleMediaEvent)
      audioElement.removeEventListener('canplay', handleMediaEvent)
      audioElement.removeEventListener('waiting', handleMediaEvent)
      audioElement.removeEventListener('error', handleMediaError)
      audioElement.removeEventListener('play', handleMediaEvent)
      audioElement.removeEventListener('playing', handleMediaEvent)
      audioElement.removeEventListener('pause', handleMediaEvent)
      audioElement.removeEventListener('ended', handleMediaEvent)
      audioElement.removeEventListener('timeupdate', handleMediaEvent)
      audioElement.removeEventListener('seeking', handleMediaEvent)
      audioElement.removeEventListener('seeked', handleMediaEvent)
      disposePreviewAudioRuntime(runtime)
    },
  }
}

export function applyPreviewAudioVolume(runtime: AudioAnalysisRuntime, previewVolume: number): void {
  if (!runtime.gainNode || !runtime.audioContext) {
    return
  }
  const targetGain = clamp(previewVolume, 0, 2)
  runtime.gainNode.gain.cancelScheduledValues(runtime.audioContext.currentTime)
  runtime.gainNode.gain.setTargetAtTime(targetGain, runtime.audioContext.currentTime, 0.06)
}

export function applyPreviewAudioMotionSmoothing(
  runtime: AudioAnalysisRuntime,
  audioMotionSmoothing: number,
): void {
  if (!runtime.analyser) {
    return
  }
  runtime.analyser.smoothingTimeConstant = clamp(audioMotionSmoothing, 0, 0.97)
}

export function applyPreviewPlaybackCommand(options: {
  command: PreviewPlaybackCommand
  runtime: AudioAnalysisRuntime
  onPlaybackStateChange: (state: VideoWorkspaceState['playback']) => void
  onPlaybackError: (message: string) => void
}): void {
  const { command, runtime, onPlaybackError, onPlaybackStateChange } = options
  const audioElement = runtime.audioElement
  const audioContext = runtime.audioContext

  if (!audioElement) {
    return
  }

  if (command.type === 'play') {
    void (async () => {
      try {
        await audioContext?.resume()
        await audioElement.play()
      } catch (error) {
        onPlaybackStateChange(buildPreviewPlaybackState(audioElement, { isPlaying: false }))
        onPlaybackError(
          error instanceof Error
            ? error.message
            : 'Preview audio could not start. Please reselect the MP3 and try again.',
        )
      }
    })()
    return
  }

  if (command.type === 'pause') {
    audioElement.pause()
    onPlaybackStateChange(buildPreviewPlaybackState(audioElement, { isPlaying: false }))
    return
  }

  if (command.type === 'stop') {
    audioElement.pause()
    audioElement.currentTime = 0
    onPlaybackStateChange(buildPreviewPlaybackState(audioElement, { isPlaying: false, currentTimeSec: 0 }))
    return
  }

  if (command.type === 'seek') {
    const durationSec = Number.isFinite(audioElement.duration) ? audioElement.duration : 0
    audioElement.currentTime = clamp(command.timeSec, 0, durationSec || command.timeSec)
    onPlaybackStateChange(buildPreviewPlaybackState(audioElement, { currentTimeSec: audioElement.currentTime, durationSec }))
  }
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value))
}
