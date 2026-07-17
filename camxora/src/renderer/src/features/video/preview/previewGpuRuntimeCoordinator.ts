import type { PreviewGpuRuntimeDraft } from '@/features/video/core/contracts/previewDraftContracts'
import type { PreviewGpuAudioSignalFrame } from '@/features/video/core/contracts/previewGpuAudioSignalContract'
import type { ParticleGpuPreparationRequest } from '@/features/video/domains/particles/particleGpuContract'
import type { SpectrumGpuPreparationRequest } from '@/features/video/domains/spectrum/spectrumGpuContract'
import type { ParticleSimulationState } from '@/features/video/domains/particles/particleSimulation'
import type { AudioSpectrumFrame } from '@/features/video/preview/audioSpectrumAnalysis'
import type { AudioAnalysisRuntime } from '@/features/video/preview/audioFeatureBus'
import type { PreviewQualityPolicy } from '@/features/video/preview/previewQualityPolicy'
import {
  preparePreviewGpuDomains,
  type PreviewGpuDomainPreparationResult,
} from '@/features/video/preview/previewGpuDomainPreparation'
import type { SpectrumLayerPreview } from '@/features/video/domains/spectrum/spectrumLayerModel'
import type { PreviewGpuRuntimeResult } from '@/features/video/preview/previewGpuRuntimeResult'
import { orchestratePreviewGpuSubmission } from '@/features/video/preview/previewGpuSubmissionOrchestrator'
import type { VideoPreviewGpuNode } from '@/features/video/preview/previewScene'
import type { SpectrumAttachment } from '@/features/video/core/scene/attachmentService'
import type { WebGpuSpectrumRenderer } from '@/features/video/webgpu/webgpuSpectrumRenderer'
import type { LogoPresentationState } from '@/features/video/domains/logo/logoPreviewRuntime'

export type PreviewGpuRuntimeCoordinatorOptions = {
  analysedFrame: AudioSpectrumFrame | null
  audioSignal: PreviewGpuAudioSignalFrame | null
  backdropSource: CanvasImageSource | null
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
  centerX: number
  centerY: number
  deltaSec: number
  dpr: number
  gpuNode: VideoPreviewGpuNode
  hasBoundAudio: boolean
  logicalHeight: number
  logicalWidth: number
  motionState: {
    flyingGlowPulseDrive: number
  }
  overlaySource: CanvasImageSource | null
  particleState: ParticleSimulationState
  qualityPolicy: PreviewQualityPolicy
  reactiveEnergy: number
  runtime: AudioAnalysisRuntime
  scale: number
  spectrumAttachment: SpectrumAttachment | null
  spectrumBarCount: number
  spectrumLayers: ReadonlyArray<SpectrumLayerPreview>
  drafts: PreviewGpuRuntimeDraft
  timeSec: number
  webgpuRenderer: WebGpuSpectrumRenderer | null
  logoPresentationState?: LogoPresentationState | null
}

export type PreviewGpuRuntimeCoordinatorResult = PreviewGpuRuntimeResult

export function runPreviewGpuRuntimeCoordinator({
  analysedFrame,
  audioSignal,
  backdropSource,
  buildLayerSpectrumValues,
  buildSyntheticSpectrumValues,
  centerX,
  centerY,
  deltaSec,
  dpr,
  gpuNode,
  hasBoundAudio,
  logicalHeight,
  logicalWidth,
  motionState,
  overlaySource,
  particleState,
  qualityPolicy,
  reactiveEnergy,
  runtime,
  scale,
  spectrumAttachment,
  spectrumBarCount,
  spectrumLayers,
  drafts,
  timeSec,
  webgpuRenderer,
  logoPresentationState,
}: PreviewGpuRuntimeCoordinatorOptions): PreviewGpuRuntimeCoordinatorResult {
  const spectrumRequest: SpectrumGpuPreparationRequest = {
    analysedFrame,
    audioSignal,
    buildLayerSpectrumValues,
    buildSyntheticSpectrumValues,
    centerX,
    centerY,
    hasBoundAudio,
    motionState,
    reactiveEnergy,
    scale,
    spectrumAttachment,
    spectrumBarCount,
    spectrumLayers,
    templateDraft: drafts.spectrum,
    timeSec,
    useWebGpuSpectrum: gpuNode.submitSpectrumInstances && Boolean(webgpuRenderer),
    logoPresentationState,
  }

  const particleRequest: ParticleGpuPreparationRequest = {
    audioSignal,
    centerX,
    centerY,
    deltaSec,
    logicalHeight,
    logicalWidth,
    particleState,
    qualityPolicy,
    reactiveEnergy,
    runtime,
    scale,
    spectrumAttachment,
    templateDraft: drafts.particles,
  }

  const domainResult: PreviewGpuDomainPreparationResult = preparePreviewGpuDomains({
    atmosphereEnabled: gpuNode.atmosphereEnabled,
    atmosphereDraft: drafts.atmosphere,
    particles: particleRequest,
    postFxDraft: drafts.postFx,
    qualityPolicy,
    reactiveEnergy,
    spectrum: spectrumRequest,
  })

  return orchestratePreviewGpuSubmission({
    backdropSource,
    dpr,
    domainResult,
    gpuNode,
    logicalHeight,
    logicalWidth,
    overlaySource,
    webgpuRenderer,
  })
}
