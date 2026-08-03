import { toRecord } from '@/features/video/domains/shared/templateValueUtils'
import {
  normalizeColor as normalizePreviewColor,
  tryParseColorToNormalizedRgb,
} from '@/features/video/preview/previewUtils'

const MAX_GRADIENT_COLOR_STOPS = 12
const GRADIENT_FALLBACK_COLOR = '#22d3ee'
const VALID_GRADIENT_DIRECTIONS = new Set([
  'left-to-right',
  'top-to-bottom',
  'diagonal',
  'radial',
  'circular',
])

export const SPECTRUM_GRADIENT_PRESET_OPTIONS: ReadonlyArray<{ label: string; value: string }> = [
  { value: '#ff4fd8,#22d3ee,#a78bfa,#f472b6', label: 'Neon Candy' },
  { value: '#38bdf8,#22d3ee,#818cf8,#c084fc', label: 'Electric Sky' },
  { value: '#fb7185,#f472b6,#e879f9,#c084fc', label: 'Hot Magenta' },
  { value: '#fb923c,#fbbf24,#f472b6,#a78bfa', label: 'Solar Pop' },
  { value: '#2dd4bf,#22d3ee,#60a5fa,#a78bfa', label: 'Mint Freeze' },
  { value: '#ff00ff,#00ffff,#a78bfa,#f472b6', label: 'Prism Beam' },
  { value: '#a3e635,#22d3ee,#818cf8,#f472b6', label: 'Lime Pulse' },
  { value: '#fb7185,#fb923c,#fbbf24,#38bdf8', label: 'Coral Wave' },
  { value: '#c084fc,#a78bfa,#67e8f9,#22d3ee', label: 'Violet Ice' },
  { value: '#fda4af,#fb7185,#f0abfc,#7dd3fc', label: 'Peach Neon' },
  { value: '#67e8f9,#22d3ee,#fb923c,#f472b6', label: 'Aqua Flame' },
  { value: '#f472b6,#a78bfa,#38bdf8,#34d399', label: 'Prism Bright' },
  { value: '#ff006e,#ffbe0b,#8338ec,#3a86ff,#fb5607', label: 'Carnival Riot' },
  { value: '#00f5d4,#00bbf9,#9b5de5,#f15bb5,#fee440', label: 'Hyper Pop' },
  { value: '#ff1744,#ff9100,#ffea00,#00e676,#2979ff,#d500f9', label: 'Rainbow Rush' },
  { value: '#ff2d95,#7b2cbf,#00d4ff,#39ff14,#ffea00', label: 'Laser Party' },
  { value: '#ff0066,#ff66cc,#66ffcc,#00ccff,#9966ff', label: 'Sugar Rush' },
  { value: '#ff5722,#ff9100,#ffc400,#76ff03,#00e5ff,#7c4dff', label: 'Spectrum Blast' },
  { value: '#e91e63,#9c27b0,#5c6bc0,#00bcd4,#8bc34a,#ffeb3b,#ff9800', label: 'Full Spectrum' },
  { value: '#ff0080,#ff8c00,#40e0d0,#7fff00,#da70d6', label: 'Tropic Neon' },
  { value: '#f72585,#ff6bcb,#c77dff,#9b5de5,#7b2cbf,#4361ee,#4895ef,#4cc9f0', label: 'Ultraviolet Sweep' },
  { value: '#ff0a54,#ff477e,#ff5c8a,#ff7096,#ff85a1,#ff99ac,#fbb1bd,#f9bec7', label: 'Hot Pink Parade' },
  { value: '#0aff99,#00f5d4,#00bbf9,#9b5de5,#f15bb5,#fee440,#ff006e', label: 'Festival Glow' },
  { value: '#39ff14,#00ff9f,#00e5ff,#2979ff,#d500f9,#ff1744,#ffea00', label: 'Cyber Rainbow' },
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
