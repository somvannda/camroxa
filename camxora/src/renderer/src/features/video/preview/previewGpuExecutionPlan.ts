import type { PreviewGpuAudioSignalFrame } from '@/features/video/core/contracts/previewGpuAudioSignalContract'
import type {
  WebGpuAtmosphereSettings,
  WebGpuParticleInstance,
  WebGpuParticleSimulationSettings,
  WebGpuPostFxSettings,
  WebGpuSpectrumGradientAtlas,
  WebGpuSpectrumInstance,
} from '@/features/video/webgpu/webgpuSpectrumRenderer'

export type PreviewGpuExecutionPlan = {
  audioSignal: PreviewGpuAudioSignalFrame | null
  atmosphere: WebGpuAtmosphereSettings | null
  backdropSource: CanvasImageSource | null
  dpr: number
  fallbackScene: boolean
  gradientAtlas: WebGpuSpectrumGradientAtlas | null
  height: number
  instances: ReadonlyArray<WebGpuSpectrumInstance>
  overlaySource: CanvasImageSource | null
  particles: ReadonlyArray<WebGpuParticleInstance>
  particleSimulation: WebGpuParticleSimulationSettings | null
  postFx: WebGpuPostFxSettings | null
  width: number
}

type BuildPreviewGpuExecutionPlanOptions = {
  audioSignal: PreviewGpuAudioSignalFrame | null
  atmosphere: WebGpuAtmosphereSettings | null
  backdropSource: CanvasImageSource | null
  dpr: number
  logicalHeight: number
  logicalWidth: number
  overlaySource: CanvasImageSource | null
  particles: ReadonlyArray<WebGpuParticleInstance>
  particleSimulation: WebGpuParticleSimulationSettings | null
  postFx: WebGpuPostFxSettings | null
  spectrumGradientAtlas: WebGpuSpectrumGradientAtlas | null
  submitFallbackScene: boolean
  submitSpectrumInstances: boolean
  spectrumInstances: ReadonlyArray<WebGpuSpectrumInstance>
}

export function buildPreviewGpuExecutionPlan({
  audioSignal,
  atmosphere,
  backdropSource,
  dpr,
  logicalHeight,
  logicalWidth,
  overlaySource,
  particles,
  particleSimulation,
  postFx,
  spectrumGradientAtlas,
  submitFallbackScene,
  submitSpectrumInstances,
  spectrumInstances,
}: BuildPreviewGpuExecutionPlanOptions): PreviewGpuExecutionPlan {
  return {
    audioSignal,
    atmosphere,
    backdropSource,
    dpr,
    fallbackScene: submitFallbackScene,
    gradientAtlas: submitSpectrumInstances ? spectrumGradientAtlas : null,
    height: logicalHeight,
    instances: submitSpectrumInstances ? spectrumInstances : [],
    overlaySource,
    particles,
    particleSimulation,
    postFx,
    width: logicalWidth,
  }
}
