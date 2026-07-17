import type { PreviewGpuExecutionPlan } from '@/features/video/preview/previewGpuExecutionPlan'
import type {
  WebGpuParticleInstance,
  WebGpuSpectrumInstance,
  WebGpuSpectrumRenderer,
} from '@/features/video/webgpu/webgpuSpectrumRenderer'

type SubmitPreviewGpuFrameOptions = PreviewGpuExecutionPlan & {
  renderer: WebGpuSpectrumRenderer | null
}

export function submitPreviewGpuFrame({
  audioSignal,
  atmosphere,
  backdropSource,
  dpr,
  fallbackScene,
  gradientAtlas,
  height,
  instances,
  overlaySource,
  particles,
  particleSimulation,
  postFx,
  renderer,
  width,
}: SubmitPreviewGpuFrameOptions): number {
  if (!renderer) {
    return 0
  }

  const renderStart = performance.now()
  renderer.render({
    width,
    height,
    dpr,
    audioSignal,
    spectrumGradientAtlas: gradientAtlas,
    instances: instances as WebGpuSpectrumInstance[],
    particles: particles as WebGpuParticleInstance[],
    particleSimulation,
    backdropSource,
    overlaySource,
    atmosphere,
    fallbackScene,
    postFx,
  })
  return performance.now() - renderStart
}
