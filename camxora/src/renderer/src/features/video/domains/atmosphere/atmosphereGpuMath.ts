import type { PreviewAtmosphereDraft } from '@/features/video/core/contracts/previewDraftContracts'
import { clamp, colorToNormalizedRgb } from '@/features/video/preview/previewUtils'
import type { WebGpuAtmosphereSettings } from '@/features/video/webgpu/webgpuSpectrumRenderer'

export function buildWebGpuAtmosphereSettings(
  draft: PreviewAtmosphereDraft,
  timeSec: number,
): WebGpuAtmosphereSettings | null {
  const smokeVisible =
    draft.smokeEnabled && clamp(draft.smokeOpacity * (0.35 + draft.smokeStrength * 0.55), 0, 0.8) > 0.001
  const vignetteVisible = draft.vignetteEnabled && clamp(draft.vignetteOpacity, 0, 1) > 0.001

  if (!smokeVisible && !vignetteVisible) {
    return null
  }

  const smokeColor = colorToNormalizedRgb(draft.smokeColor)
  const vignetteColor = colorToNormalizedRgb(draft.vignetteColor)
  return {
    timeSec,
    smokeEnabled: smokeVisible,
    smokeOpacity: clamp(draft.smokeOpacity, 0, 1),
    smokeStrength: clamp(draft.smokeStrength, 0, 1),
    smokeBlur: clamp(draft.smokeBlur, 0, 1),
    smokeNoise: clamp(draft.smokeNoise, 0, 1),
    smokeSpeed: Math.max(0.2, draft.smokeSpeed),
    smokeRed: smokeColor.red,
    smokeGreen: smokeColor.green,
    smokeBlue: smokeColor.blue,
    vignetteEnabled: vignetteVisible,
    vignetteStrength: clamp(draft.vignetteStrength, 0, 1),
    vignetteFeather: clamp(draft.vignetteFeather, 0.05, 1),
    vignetteOpacity: clamp(draft.vignetteOpacity, 0, 1),
    vignetteRed: vignetteColor.red,
    vignetteGreen: vignetteColor.green,
    vignetteBlue: vignetteColor.blue,
  }
}
