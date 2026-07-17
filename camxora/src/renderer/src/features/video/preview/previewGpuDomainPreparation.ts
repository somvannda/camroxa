import type {
  AtmosphereGpuPreparationRequest,
} from '@/features/video/domains/atmosphere/atmosphereGpuRuntime'
import { buildAtmosphereGpuSettings } from '@/features/video/domains/atmosphere/atmosphereGpuRuntime'
import type {
  PreviewAtmosphereDraft,
  PreviewGpuPostFxDraft,
} from '@/features/video/core/contracts/previewDraftContracts'
import type {
  ParticleGpuPreparationRequest,
  ParticleGpuPreparationResult,
} from '@/features/video/domains/particles/particleGpuContract'
import { buildParticleGpuState } from '@/features/video/domains/particles/particleGpuRuntime'
import type {
  SpectrumGpuPreparationRequest,
  SpectrumGpuPreparationResult,
} from '@/features/video/domains/spectrum/spectrumGpuContract'
import { buildSpectrumGpuInstances } from '@/features/video/domains/spectrum/spectrumGpuRuntime'
import {
  buildPreviewGpuPostFxPlan,
  mapPreviewGpuPostFxPlanToWebGpuSettings,
  type PreviewGpuPostFxPlan,
} from '@/features/video/preview/previewGpuPostFx'
import type { PreviewGpuAudioSignalFrame } from '@/features/video/core/contracts/previewGpuAudioSignalContract'
import type { PreviewQualityPolicy } from '@/features/video/preview/previewQualityPolicy'
import type {
  WebGpuAtmosphereSettings,
  WebGpuParticleInstance,
  WebGpuParticleSimulationSettings,
  WebGpuPostFxSettings,
  WebGpuSpectrumGradientAtlas,
  WebGpuSpectrumInstance,
} from '@/features/video/webgpu/webgpuSpectrumRenderer'

type PreparePreviewGpuDomainsOptions = {
  atmosphereEnabled: boolean
  atmosphereDraft: PreviewAtmosphereDraft
  particles: ParticleGpuPreparationRequest
  postFxDraft: PreviewGpuPostFxDraft
  qualityPolicy: PreviewQualityPolicy
  reactiveEnergy: number
  spectrum: SpectrumGpuPreparationRequest
}

export type PreviewGpuDomainPreparationResult = {
  audioSignal: PreviewGpuAudioSignalFrame | null
  gpuInstances: WebGpuSpectrumInstance[]
  gradientAtlas: WebGpuSpectrumGradientAtlas | null
  gpuParticles: WebGpuParticleInstance[]
  gpuParticleSimulation: WebGpuParticleSimulationSettings | null
  atmosphere: WebGpuAtmosphereSettings | null
  postFxPlan: PreviewGpuPostFxPlan | null
  postFx: WebGpuPostFxSettings | null
  hasPostFx: boolean
  timing: {
    instancesMs: number
    particlesMs: number
  }
}

export function preparePreviewGpuDomains({
  atmosphereEnabled,
  atmosphereDraft,
  particles,
  postFxDraft,
  qualityPolicy,
  reactiveEnergy,
  spectrum,
}: PreparePreviewGpuDomainsOptions): PreviewGpuDomainPreparationResult {
  const atmosphereRequest: AtmosphereGpuPreparationRequest = {
    atmosphereEnabled,
    templateDraft: atmosphereDraft,
    timeSec: spectrum.timeSec,
  }

  const { gpuInstances, gradientAtlas, instancesMs }: SpectrumGpuPreparationResult =
    buildSpectrumGpuInstances(spectrum)

  const { gpuParticles, gpuParticleSimulation, particlesMs }: ParticleGpuPreparationResult =
    buildParticleGpuState(particles)

  const atmosphere = buildAtmosphereGpuSettings(atmosphereRequest)
  const postFxPlan = buildPreviewGpuPostFxPlan({
    qualityPolicy,
    reactiveEnergy,
    spectrumLayers: spectrum.spectrumLayers,
    templateDraft: postFxDraft,
  })
  const postFx = mapPreviewGpuPostFxPlanToWebGpuSettings(postFxPlan)
  const hasPostFx = Boolean(postFxPlan?.enabled)

  return {
    audioSignal: spectrum.audioSignal,
    gpuInstances,
    gradientAtlas,
    gpuParticles,
    gpuParticleSimulation,
    atmosphere,
    postFxPlan,
    postFx,
    hasPostFx,
    timing: {
      instancesMs,
      particlesMs,
    },
  }
}
