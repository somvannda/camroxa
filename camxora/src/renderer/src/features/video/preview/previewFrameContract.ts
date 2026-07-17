import type { MutableRefObject } from 'react'

import type { PreviewLogoDrawDraft } from '@/features/video/core/contracts/previewDraftContracts'
import type { BackgroundPresentationState } from '@/features/video/domains/background/backgroundPreviewRuntime'
import type { LogoPresentationState } from '@/features/video/domains/logo/logoPreviewRuntime'
import type { ParticleSimulationState } from '@/features/video/domains/particles/particleSimulation'
import type { AudioSpectrumFrame } from '@/features/video/preview/audioSpectrumAnalysis'
import type { AudioAnalysisRuntime } from '@/features/video/preview/audioFeatureBus'
import type { PreviewFrameTelemetryReport } from '@/features/video/preview/previewFrameTelemetry'
import type { PreviewReactiveMotionState } from '@/features/video/preview/previewReactiveFrameState'
import type { VideoPreviewScene } from '@/features/video/preview/previewScene'
import type { WebGpuSpectrumRenderer } from '@/features/video/webgpu/webgpuSpectrumRenderer'
import type { VideoWorkspaceState } from '@/shared/types/desktop'

export type PreviewRuntimeOptions<TOverlay> = {
  audioRuntimeRef: MutableRefObject<AudioAnalysisRuntime>
  backdropCanvasRef: MutableRefObject<HTMLCanvasElement | null>
  backgroundImageRef: MutableRefObject<HTMLImageElement | null>
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
  domBackgroundImageRef: MutableRefObject<HTMLImageElement | null>
  domLogoLayerRef: MutableRefObject<HTMLDivElement | null>
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
  logoImageRef: MutableRefObject<HTMLImageElement | null>
  overlayCanvasRef: MutableRefObject<HTMLCanvasElement | null>
  particleStateRef: MutableRefObject<ParticleSimulationState>
  previewMotionRef: MutableRefObject<PreviewReactiveMotionState>
  reportPlaybackState: (nextState: VideoWorkspaceState['playback'], force?: boolean) => void
  runtimeMode?: 'live' | 'manual-export'
  resolveAnchorPoint: (anchor: string, width: number, height: number) => { x: number; y: number }
  scene: VideoPreviewScene<TOverlay>
  smoothPreviewReactiveValue: (
    current: number,
    target: number,
    deltaSec: number,
    smoothing: number,
  ) => number
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
  webgpuCanvasRef: MutableRefObject<HTMLCanvasElement | null>
  webgpuRendererRef: MutableRefObject<WebGpuSpectrumRenderer | null>
  averageValues: (values: ArrayLike<number>, count?: number) => number
  applyDomBackgroundPresentation: (
    node: HTMLImageElement,
    presentation: BackgroundPresentationState,
  ) => void
  applyDomLogoPresentation: (
    node: HTMLDivElement,
    presentation: LogoPresentationState,
  ) => void
  onTelemetryReport?: (report: PreviewFrameTelemetryReport) => void
  lastPlaybackReportAtRef: MutableRefObject<number>
}

export type PreviewFrameExecutionOptions<TOverlay> = Omit<
  PreviewRuntimeOptions<TOverlay>,
  'runtimeMode' | 'webgpuCanvasRef'
>
