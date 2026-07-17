import type { PreviewGpuSpectrumDraft } from '@/features/video/core/contracts/previewDraftContracts'
import type { PreviewGpuAudioSignalFrame } from '@/features/video/core/contracts/previewGpuAudioSignalContract'
import type { LogoPresentationState, SpectrumAttachment } from '@/features/video/core/scene/attachmentService'
import type { SpectrumLayerPreview } from '@/features/video/domains/spectrum/spectrumLayerModel'
import type { AudioSpectrumFrame } from '@/features/video/preview/audioSpectrumAnalysis'
import type {
  WebGpuSpectrumGradientAtlas,
  WebGpuSpectrumInstance,
} from '@/features/video/webgpu/webgpuSpectrumRenderer'

export type SpectrumGpuMotionState = {
  flyingGlowPulseDrive: number
}

export type SpectrumGpuPreparationRequest = {
  analysedFrame: AudioSpectrumFrame | null
  audioSignal: PreviewGpuAudioSignalFrame | null
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
  hasBoundAudio: boolean
  motionState: SpectrumGpuMotionState
  reactiveEnergy: number
  scale: number
  spectrumAttachment: SpectrumAttachment | null
  spectrumBarCount: number
  spectrumLayers: readonly SpectrumLayerPreview[]
  templateDraft: PreviewGpuSpectrumDraft
  timeSec: number
  useWebGpuSpectrum: boolean
  logoPresentationState?: LogoPresentationState | null
}

export type SpectrumGpuPreparationResult = {
  gradientAtlas: WebGpuSpectrumGradientAtlas | null
  gpuInstances: WebGpuSpectrumInstance[]
  instancesMs: number
}
