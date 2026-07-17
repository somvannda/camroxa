import {
  buildPreviewGpuExecutionPlan,
  type PreviewGpuExecutionPlan,
} from '@/features/video/preview/previewGpuExecutionPlan'
import type { PreviewGpuDomainPreparationResult } from '@/features/video/preview/previewGpuDomainPreparation'
import {
  buildPreviewGpuRuntimeResult,
  type PreviewGpuRuntimeResult,
} from '@/features/video/preview/previewGpuRuntimeResult'
import { submitPreviewGpuFrame } from '@/features/video/preview/previewGpuSubmission'
import type { VideoPreviewGpuNode } from '@/features/video/preview/previewScene'
import type { WebGpuSpectrumRenderer } from '@/features/video/webgpu/webgpuSpectrumRenderer'

type OrchestratePreviewGpuSubmissionOptions = {
  backdropSource: CanvasImageSource | null
  dpr: number
  domainResult: PreviewGpuDomainPreparationResult
  gpuNode: VideoPreviewGpuNode
  logicalHeight: number
  logicalWidth: number
  overlaySource: CanvasImageSource | null
  webgpuRenderer: WebGpuSpectrumRenderer | null
}

export function orchestratePreviewGpuSubmission({
  backdropSource,
  dpr,
  domainResult,
  gpuNode,
  logicalHeight,
  logicalWidth,
  overlaySource,
  webgpuRenderer,
}: OrchestratePreviewGpuSubmissionOptions): PreviewGpuRuntimeResult {
  const executionPlan: PreviewGpuExecutionPlan = buildPreviewGpuExecutionPlan({
    audioSignal: domainResult.audioSignal,
    atmosphere: domainResult.atmosphere,
    backdropSource,
    dpr,
    logicalHeight,
    logicalWidth,
    overlaySource,
    particles: domainResult.gpuParticles,
    particleSimulation: domainResult.gpuParticleSimulation,
    postFx: domainResult.postFx,
    spectrumGradientAtlas: domainResult.gradientAtlas,
    submitFallbackScene: gpuNode.submitFallbackScene,
    submitSpectrumInstances: gpuNode.submitSpectrumInstances,
    spectrumInstances: domainResult.gpuInstances,
  })

  const renderMs = submitPreviewGpuFrame({
    ...executionPlan,
    renderer: webgpuRenderer,
  })

  return buildPreviewGpuRuntimeResult({
    gpuInstances: domainResult.gpuInstances,
    gpuParticles: domainResult.gpuParticles,
    gpuParticleSimulation: domainResult.gpuParticleSimulation,
    hasPostFx: domainResult.hasPostFx,
    instancesMs: domainResult.timing.instancesMs,
    particlesMs: domainResult.timing.particlesMs,
    renderMs,
  })
}
