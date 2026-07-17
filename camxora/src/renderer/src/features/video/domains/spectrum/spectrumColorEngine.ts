import { toRecord } from '@/features/video/domains/shared/templateValueUtils'
import {
  normalizeColor as normalizePreviewColor,
  tryParseColorToNormalizedRgb,
} from '@/features/video/preview/previewUtils'

const MAX_GRADIENT_COLOR_STOPS = 5
const GRADIENT_FALLBACK_COLOR = '#22d3ee'
const VALID_GRADIENT_DIRECTIONS = new Set([
  'left-to-right',
  'top-to-bottom',
  'diagonal',
  'radial',
  'circular',
])

export const SPECTRUM_GRADIENT_PRESET_OPTIONS: ReadonlyArray<{ label: string; value: string }> = [
  { value: '#ff00ff,#00ffff', label: 'Cyber Blue' },
  { value: '#ff8800,#ff0000', label: 'EDM Fire' },
  { value: '#00ff00,#ffff00', label: 'Toxic' },
  { value: '#8a2be2,#4b0082', label: 'Galaxy' },
  { value: '#00ffff,#ffffff', label: 'Ice' },
  { value: '#ff4500,#ff1493', label: 'Lava' },
  { value: '#ff8c00,#ff69b4', label: 'Sunset' },
  { value: '#ff0000,#00ff00,#0000ff', label: 'RGB Flow' },
  { value: '#ffffff,#ec4899,#8b5cf6,#22d3ee', label: 'Aurora' },
  { value: '#fde68a,#fb7185,#c084fc,#60a5fa', label: 'Festival' },
  { value: '#22c55e,#14b8a6,#06b6d4,#3b82f6', label: 'Emerald Wave' },
  { value: '#ffffff,#f472b6,#fde68a,#f97316,#ef4444', label: 'Solar Bloom' },
] as const

export type SpectrumColorMode = 'solid' | 'gradient'

export type SpectrumLayerColorModel = {
  mode: SpectrumColorMode
  solidColor: string
  gradientDirection: string
  gradientColors: string[]
  colors: string[]
}

export type SpectrumLayerColorPatch = Partial<{
  mode: string
  solidColor: string
  gradientDirection: string
  gradientColors: unknown[]
}>

function normalizeSpectrumColor(value: unknown, fallback: string): string {
  const raw = typeof value === 'string' ? value.trim() : ''
  if (!raw) {
    return fallback
  }

  const normalized = normalizePreviewColor(raw, fallback)
  return tryParseColorToNormalizedRgb(normalized) ? normalized : fallback
}

function extractColorValue(value: unknown): string {
  if (typeof value === 'string') {
    return value
  }

  const record = toRecord(value)
  return String(record.color ?? record.value ?? record.hex ?? record.solidColor ?? '').trim()
}

function normalizeSpectrumColorMode(value: unknown): SpectrumColorMode {
  return String(value ?? 'solid').trim().toLowerCase() === 'gradient' ? 'gradient' : 'solid'
}

function normalizeSpectrumGradientDirection(value: unknown): string {
  const normalized = String(value ?? 'left-to-right').trim().toLowerCase()
  return VALID_GRADIENT_DIRECTIONS.has(normalized) ? normalized : 'left-to-right'
}

export function getSpectrumLayerColorFallback(index: number): string {
  return index % 2 === 0 ? '#8b5cf6' : '#22d3ee'
}

export function normalizeSpectrumGradientColors(
  rawColors: ReadonlyArray<unknown>,
  fallback: string,
): string[] {
  const normalized = rawColors
    .map((value) => normalizeSpectrumColor(extractColorValue(value), ''))
    .filter(Boolean)
    .slice(0, MAX_GRADIENT_COLOR_STOPS)

  if (normalized.length >= 2) {
    return normalized
  }

  if (normalized.length === 1) {
    return [normalized[0], GRADIENT_FALLBACK_COLOR]
  }

  return [fallback, GRADIENT_FALLBACK_COLOR]
}

export function extractSpectrumLayerColorModel(
  layerRecord: Record<string, unknown> | null | undefined,
  fallback: string,
): SpectrumLayerColorModel {
  const record = layerRecord ?? {}
  const nestedColorRecord = toRecord(record.color)
  const rawColorRecord =
    Object.keys(nestedColorRecord).length > 0
      ? nestedColorRecord
      : {
          mode: record.colorMode,
          solidColor: record.solidColor,
          gradientDirection: record.gradientDirection,
          gradientColors: record.gradientColors,
        }

  const mode = normalizeSpectrumColorMode(rawColorRecord.mode)
  const solidColor = normalizeSpectrumColor(
    rawColorRecord.solidColor ?? rawColorRecord.color ?? rawColorRecord.value,
    fallback,
  )
  const gradientDirection = normalizeSpectrumGradientDirection(rawColorRecord.gradientDirection)
  const gradientColors = normalizeSpectrumGradientColors(
    Array.isArray(rawColorRecord.gradientColors) ? rawColorRecord.gradientColors : [],
    solidColor,
  )

  return {
    mode,
    solidColor,
    gradientDirection,
    gradientColors,
    colors: mode === 'gradient' ? gradientColors : [solidColor],
  }
}

export function buildSpectrumGradientPresetValue(colors: ReadonlyArray<string>): string {
  return colors.join(',')
}

export function applySpectrumLayerColorPatch(
  layerRecord: Record<string, unknown>,
  patch: SpectrumLayerColorPatch,
  fallback: string,
): Record<string, unknown> {
  const currentColor = extractSpectrumLayerColorModel(layerRecord, fallback)
  const nextMode = patch.mode === undefined ? currentColor.mode : normalizeSpectrumColorMode(patch.mode)
  const nextSolidColor =
    patch.solidColor === undefined
      ? currentColor.solidColor
      : normalizeSpectrumColor(patch.solidColor, currentColor.solidColor)
  const nextGradientDirection =
    patch.gradientDirection === undefined
      ? currentColor.gradientDirection
      : normalizeSpectrumGradientDirection(patch.gradientDirection)
  const nextGradientColors =
    patch.gradientColors === undefined
      ? currentColor.gradientColors
      : normalizeSpectrumGradientColors(patch.gradientColors, nextSolidColor)
  const currentNestedColor = toRecord(layerRecord.color)

  return {
    ...layerRecord,
    colorMode: nextMode,
    solidColor: nextSolidColor,
    gradientColors: nextGradientColors,
    gradientDirection: nextGradientDirection,
    color: {
      ...currentNestedColor,
      mode: nextMode,
      solidColor: nextSolidColor,
      gradientColors: nextGradientColors,
      gradientDirection: nextGradientDirection,
    },
  }
}
