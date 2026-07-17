import type { CSSProperties, MutableRefObject } from 'react'

import type { PreviewLogoDrawDraft } from '@/features/video/core/contracts/previewDraftContracts'
import type { PreviewLifecycleState } from '@/features/video/preview/previewLifecycleState'
import type { VideoTemplateDraft } from '@/features/video/core/contracts/videoTemplateDraft'
import type { BackgroundPresentationState } from '@/features/video/domains/background/backgroundPreviewRuntime'
import type { LogoPresentationState } from '@/features/video/domains/logo/logoPreviewRuntime'
import type { AudioSpectrumFrame } from '@/features/video/preview/audioSpectrumAnalysis'
import type { PreviewPerformanceVerification } from '@/features/video/preview/previewPerformanceVerification'
import type { VideoPreviewScene } from '@/features/video/preview/previewScene'
import type { WebGpuSpectrumRenderer } from '@/features/video/webgpu/webgpuSpectrumRenderer'
import type {
  BuildDomBackgroundStyleOptions,
  BuildDomLogoStyleOptions,
  ResolveSpectrumBarCountOptions,
  ResolveTextOverlayStateOptions,
  ResolveTextOverlayStateResult,
} from '@/features/video/preview/usePreviewSceneState'
import type { PreviewPlaybackCommand } from '@/features/video/preview/transportClock'
import type { VideoWorkspaceState } from '@/shared/types/desktop'

export type PreviewManualRenderFrameOptions = {
  previousTimestampMs: number
  timestampMs: number
  playbackTimeSec?: number
}

export type PreviewProviderRenderState<TOverlay> = {
  containerRef: MutableRefObject<HTMLDivElement | null>
  domBackgroundImageRef: MutableRefObject<HTMLImageElement | null>
  domLogoLayerRef: MutableRefObject<HTMLDivElement | null>
  lifecycleState: PreviewLifecycleState
  manualRenderFrame: ((options: PreviewManualRenderFrameOptions) => void) | null
  playbackReady: boolean
  performanceVerification: PreviewPerformanceVerification | null
  scene: VideoPreviewScene<TOverlay>
  webgpuCanvasRef: MutableRefObject<HTMLCanvasElement | null>
  webgpuRendererRef: MutableRefObject<WebGpuSpectrumRenderer | null>
}

export type PreviewProviderOptions<TOverlay> = {
  backgroundPath: string
  buildDomBackgroundStyle: (options: BuildDomBackgroundStyleOptions) => CSSProperties
  buildDomLogoStyle: (options: BuildDomLogoStyleOptions) => CSSProperties
  buildLayerSpectrumValues: (
    count: number,
    frame: AudioSpectrumFrame | null,
    mirrored: boolean,
  ) => number[] | null
  buildSyntheticSpectrumValues: (
    count: number,
    timeSec: number,
    sensitivity: number,
    smoothing: number,
    layerIndex: number,
  ) => number[]
  drawBackgroundLayer: (
    context: CanvasRenderingContext2D,
    backgroundImage: HTMLImageElement | null,
    width: number,
    height: number,
    presentation: BackgroundPresentationState,
  ) => void
  drawLogoLayer: (
    context: CanvasRenderingContext2D,
    draft: PreviewLogoDrawDraft,
    logoImage: HTMLImageElement | null,
    presentation: LogoPresentationState,
  ) => void
  drawTextOverlays: (
    context: CanvasRenderingContext2D,
    overlays: ReadonlyArray<TOverlay>,
    width: number,
    height: number,
  ) => void
  logoPath: string
  onPlaybackStateChange?: (state: VideoWorkspaceState['playback']) => void
  playbackCommand: PreviewPlaybackCommand | null
  previewVolume: number
  runtimeMode?: 'live' | 'manual-export'
  resolveAnchorPoint: (anchor: string, width: number, height: number) => { x: number; y: number }
  resolveSpectrumBarCount: (options: ResolveSpectrumBarCountOptions) => number
  resolveTextOverlayState: (
    options: ResolveTextOverlayStateOptions,
  ) => ResolveTextOverlayStateResult<TOverlay>
  selectedMp3Path: string
  selectedTextOverlayIndex: number
  smoothPreviewReactiveValue: (
    current: number,
    target: number,
    deltaSec: number,
    smoothing: number,
  ) => number
  template: Record<string, unknown>
  templateDraft: VideoTemplateDraft
  updateFlyingGlowWingEnvelope: (
    currentPulse: number,
    supportDrive: number,
    triggerDrive: number,
    lastTriggerDrive: number,
    timeSec: number,
    deltaSec: number,
    lastTriggerSec: number,
    beatIntervalSec: number,
    motionSpeed: number,
    releaseControl: number,
  ) => {
    pulseDrive: number
    lastTriggerDrive: number
    lastTriggerSec: number
    beatIntervalSec: number
  }
  averageValues: (values: ArrayLike<number>, count?: number) => number
  applyDomBackgroundPresentation: (
    node: HTMLImageElement,
    presentation: BackgroundPresentationState,
  ) => void
  applyDomLogoPresentation: (
    node: HTMLDivElement,
    presentation: LogoPresentationState,
  ) => void
  workspace: Pick<VideoWorkspaceState, 'previewAspectRatio' | 'playback'>
}
