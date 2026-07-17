import type {
  WebGpuParticleInstance,
  WebGpuParticleSimulationSettings,
  WebGpuSpectrumInstance,
} from '@/features/video/webgpu/webgpuSpectrumRenderer'

export type PreviewGpuRuntimeResult = {
  gpuInstances: WebGpuSpectrumInstance[]
  gpuParticles: WebGpuParticleInstance[]
  gpuParticleSimulation: WebGpuParticleSimulationSettings | null
  hasPostFx: boolean
  timing: {
    instancesMs: number
    particlesMs: number
    renderMs: number
  }
}

type BuildPreviewGpuRuntimeResultOptions = {
  gpuInstances: WebGpuSpectrumInstance[]
  gpuParticles: WebGpuParticleInstance[]
  gpuParticleSimulation: WebGpuParticleSimulationSettings | null
  hasPostFx: boolean
  instancesMs: number
  particlesMs: number
  renderMs: number
}

export function buildPreviewGpuRuntimeResult({
  gpuInstances,
  gpuParticles,
  gpuParticleSimulation,
  hasPostFx,
  instancesMs,
  particlesMs,
  renderMs,
}: BuildPreviewGpuRuntimeResultOptions): PreviewGpuRuntimeResult {
  return {
    gpuInstances,
    gpuParticles,
    gpuParticleSimulation,
    hasPostFx,
    timing: {
      instancesMs,
      particlesMs,
      renderMs,
    },
  }
}
