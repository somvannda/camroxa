import {
  extractSpectrumLayerColorModel,
  getSpectrumLayerColorFallback,
  type SpectrumColorMode,
} from '@/features/video/domains/spectrum/spectrumColorEngine'
import { toBoolean, toNumber, toRecord } from '@/features/video/domains/shared/templateValueUtils'
import { clamp } from '@/features/video/preview/previewUtils'

export type SpectrumLayerPreview = {
  id: string
  styleKey: string
  colorMode: SpectrumColorMode
  gradientDirection: string
  radiusOffset: number
  thickness: number
  barWidth: number
  solidBand: boolean
  opacity: number
  glow: number
  blur: number
  curved: boolean
  mirrored: boolean
  fillCircle: boolean
  gravity: string
  blendMode: string
  colors: string[]
}

export function normalizeSpectrumStyleKey(styleKey: string): string {
  const normalized = String(styleKey || '').trim().toLowerCase()
  if (!normalized) {
    return 'straight-bars'
  }

  switch (normalized) {
    case 'symmetrical':
      return 'symmetrical-bars'
    case 'triple-neon-halo':
      return 'halo-stack'
    case 'bass-vortex-stack':
      return 'liquid'
    case 'soft-aura-stack':
      return 'soft-waveform'
    default:
      return normalized
  }
}

export function buildSpectrumLayers(template: Record<string, unknown>): SpectrumLayerPreview[] {
  const rawLayers = Array.isArray(template.layers) ? template.layers : []
  const styleKey = normalizeSpectrumStyleKey(String(template.style ?? 'straight-bars'))
  const layers: Array<SpectrumLayerPreview | null> = rawLayers
    .map((layer, index) => {
      const record = toRecord(layer)
      if (!toBoolean(record.enabled, true)) {
        return null
      }

      const colorModel = extractSpectrumLayerColorModel(record, getSpectrumLayerColorFallback(index))
      return {
        id: String(record.id ?? `layer-${index + 1}`),
        styleKey,
        colorMode: colorModel.mode,
        gradientDirection: colorModel.gradientDirection,
        radiusOffset: toNumber(record.radiusOffset, index * 18),
        thickness: clamp(toNumber(record.thickness, 42), 8, 180),
        barWidth: clamp(toNumber(record.barWidth, 3), 1, 120),
        solidBand: toBoolean(record.solidBand, false),
        opacity: clamp(toNumber(record.opacity, 1), 0.15, 1),
        glow: clamp(toNumber(record.glow, 18), 0, 120),
        blur: clamp(toNumber(record.blur, 0), 0, 48),
        curved: toBoolean(record.curved, true),
        mirrored: toBoolean(record.mirrored, true),
        fillCircle: toBoolean(record.fillCircle, false),
        gravity: String(record.gravity ?? 'bottom').trim().toLowerCase() || 'bottom',
        blendMode: String(record.blend_mode ?? 'normal').trim().toLowerCase() || 'normal',
        colors: colorModel.colors,
      }
    })
  return layers.filter((layer): layer is SpectrumLayerPreview => layer !== null)
}
