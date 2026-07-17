import type { PreviewParticleRuntimeDraft } from '@/features/video/core/contracts/previewDraftContracts'
import type { SpectrumAttachment } from '@/features/video/core/scene/attachmentService'
import type { PreviewGpuAudioSignalFrame } from '@/features/video/core/contracts/previewGpuAudioSignalContract'
import type { AudioAnalysisRuntime } from '@/features/video/preview/audioFeatureBus'
import type { PreviewQualityPolicy } from '@/features/video/preview/previewQualityPolicy'
import type { ParticleSimulationState } from '@/features/video/domains/particles/particleSimulation'
import type {
  WebGpuParticleInstance,
  WebGpuParticleSimulationSettings,
} from '@/features/video/webgpu/webgpuSpectrumRenderer'

export type ParticleGpuPreparationRequest = {
  centerX: number
  centerY: number
  deltaSec: number
  logicalHeight: number
  logicalWidth: number
  particleState: ParticleSimulationState
  qualityPolicy: PreviewQualityPolicy
  audioSignal: PreviewGpuAudioSignalFrame | null
  reactiveEnergy: number
  runtime: AudioAnalysisRuntime
  scale: number
  spectrumAttachment: SpectrumAttachment | null
  templateDraft: PreviewParticleRuntimeDraft
}

export type ParticleGpuPreparationResult = {
  gpuParticles: WebGpuParticleInstance[]
  gpuParticleSimulation: WebGpuParticleSimulationSettings | null
  particlesMs: number
}
