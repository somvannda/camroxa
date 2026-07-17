import type { PreviewAtmosphereDraft } from '@/features/video/core/contracts/previewDraftContracts'
import { buildWebGpuAtmosphereSettings } from '@/features/video/domains/atmosphere/atmosphereGpuMath'
import type { WebGpuAtmosphereSettings } from '@/features/video/webgpu/webgpuSpectrumRenderer'

export type AtmosphereGpuPreparationRequest = {
  atmosphereEnabled: boolean
  templateDraft: PreviewAtmosphereDraft
  timeSec: number
}

export function buildAtmosphereGpuSettings({
  atmosphereEnabled,
  templateDraft,
  timeSec,
}: AtmosphereGpuPreparationRequest): WebGpuAtmosphereSettings | null {
  if (!atmosphereEnabled) {
    return null
  }

  return buildWebGpuAtmosphereSettings(templateDraft, timeSec)
}
