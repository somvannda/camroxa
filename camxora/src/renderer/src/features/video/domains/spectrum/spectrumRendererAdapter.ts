import type { SpectrumLayerPreview } from '@/features/video/domains/spectrum/spectrumLayerModel'
import { normalizeSpectrumStyleKey } from '@/features/video/domains/spectrum/spectrumLayerModel'
import { clamp, colorToNormalizedRgb } from '@/features/video/preview/previewUtils'
import type {
  WebGpuSpectrumGradientAtlas,
  WebGpuSpectrumInstance,
} from '@/features/video/webgpu/webgpuSpectrumRenderer'

type SpectrumRenderPass = {
  isGlow: boolean
  foundationRing?: boolean
  alpha: number
  barWidth: number
  thickness: number
  solidBand: boolean
  fillCircle: boolean
  glow: number
  blur: number
  blendMode: string
}

type SpectrumSampleGeometry = {
  baseX: number
  baseY: number
  dirX: number
  dirY: number
}

type FlyingWingProfile = {
  shoulderBias: number
  centerDip: number
  topFocus: number
  lengthBias: number
  widthBias: number
  glowBias: number
  travelBias: number
  travelLift: number
}

function interpolateColor(channelA: number, channelB: number, mixAmount: number): number {
  return channelA + (channelB - channelA) * mixAmount
}

function wrapAngleToPi(angle: number): number {
  let normalized = angle
  while (normalized <= -Math.PI) {
    normalized += Math.PI * 2
  }
  while (normalized > Math.PI) {
    normalized -= Math.PI * 2
  }
  return normalized
}

function sampleBellCurve(value: number, center: number, width: number): number {
  const normalized = (value - center) / Math.max(0.0001, width)
  return Math.exp(-(normalized * normalized))
}

function smoothstep01(value: number): number {
  const t = clamp(value, 0, 1)
  return t * t * (3 - 2 * t)
}

function smoothCircularValues(values: number[]): number[] {
  if (values.length <= 2) {
    return values.slice()
  }

  const kernel = [0.08, 0.14, 0.2, 0.16, 0.2, 0.14, 0.08] as const
  const radius = Math.floor(kernel.length / 2)
  return values.map((value, index) => {
    let total = 0
    for (let offset = -radius; offset <= radius; offset += 1) {
      const sampleIndex = (index + offset + values.length) % values.length
      total += (values[sampleIndex] ?? value) * kernel[offset + radius]
    }
    return clamp(total, 0, 1)
  })
}

function smoothCircularValuesStrong(values: number[]): number[] {
  return smoothCircularValues(smoothCircularValues(values))
}

function interpolateCircularValues(values: number[], targetCount: number): number[] {
  if (values.length === 0) {
    return []
  }
  if (values.length === 1 || targetCount <= values.length) {
    return values.slice()
  }

  return Array.from({ length: targetCount }, (_, index) => {
    const position = (index / targetCount) * values.length
    const lowerIndex = Math.floor(position) % values.length
    const upperIndex = (lowerIndex + 1) % values.length
    const mixAmount = position - Math.floor(position)
    const lower = values[lowerIndex] ?? 0
    const upper = values[upperIndex] ?? lower
    return clamp(lower + (upper - lower) * mixAmount, 0, 1)
  })
}

function buildFlyingGlowContinuousValues(values: number[]): number[] {
  if (values.length <= 1) {
    return values.slice()
  }

  const targetCount = Math.max(360, Math.min(960, values.length * 8))
  const interpolated = interpolateCircularValues(values, targetCount)
  const smoothed = smoothCircularValuesStrong(interpolated)
  return smoothed.map((value, index) => clamp(value * 0.88 + (interpolated[index] ?? value) * 0.12, 0, 1))
}

function resolveGradientSampleProgress(
  layer: SpectrumLayerPreview,
  progress: number,
  value: number,
  centerBias: number,
): number {
  switch (layer.gradientDirection) {
    case 'top-to-bottom':
      return clamp(1 - value, 0, 1)
    case 'diagonal':
      return clamp(progress * 0.65 + (1 - value) * 0.35, 0, 1)
    case 'radial':
      return clamp(centerBias, 0, 1)
    case 'circular':
      return clamp(progress, 0, 1)
    case 'left-to-right':
    default:
      return clamp(progress, 0, 1)
  }
}

function resolveFlyingGlowGradientSampleProgress(
  layer: SpectrumLayerPreview,
  progress: number,
  sample: SpectrumSampleGeometry,
  centerX: number,
  centerY: number,
  radiusBase: number,
): number {
  const safeRadius = Math.max(1, radiusBase)
  const normalizedX = clamp((sample.baseX - centerX) / safeRadius, -1, 1)
  const normalizedY = clamp((sample.baseY - centerY) / safeRadius, -1, 1)
  const horizontal = (normalizedX + 1) * 0.5
  const vertical = (normalizedY + 1) * 0.5

  switch (layer.gradientDirection) {
    case 'top-to-bottom':
      return clamp(vertical, 0, 1)
    case 'diagonal':
      return clamp((horizontal + vertical) * 0.5, 0, 1)
    case 'radial':
      // A curved ring has effectively constant radius, so fall back to circular travel
      // instead of collapsing the whole body to one sampled color.
      return clamp(progress, 0, 1)
    case 'circular':
      return clamp(progress, 0, 1)
    case 'left-to-right':
    default:
      return clamp(horizontal, 0, 1)
  }
}

function sampleGradientPaletteColor(
  colors: ReadonlyArray<string>,
  sampleProgress: number,
): { red: number; green: number; blue: number } {
  if (colors.length <= 1) {
    return colorToNormalizedRgb(colors[0] ?? '#ffffff')
  }

  const scaledIndex = clamp(sampleProgress, 0, 1) * (colors.length - 1)
  const lowerIndex = Math.floor(scaledIndex)
  const upperIndex = Math.min(colors.length - 1, Math.ceil(scaledIndex))
  const mixAmount = scaledIndex - lowerIndex
  const lower = colorToNormalizedRgb(colors[lowerIndex] ?? '#ffffff')
  const upper = colorToNormalizedRgb(
    colors[upperIndex] ?? colors[lowerIndex] ?? '#ffffff',
  )

  return {
    red: interpolateColor(lower.red, upper.red, mixAmount),
    green: interpolateColor(lower.green, upper.green, mixAmount),
    blue: interpolateColor(lower.blue, upper.blue, mixAmount),
  }
}

const SPECTRUM_GRADIENT_ATLAS_WIDTH = 256

export function buildWebGpuSpectrumGradientAtlas(
  layers: ReadonlyArray<SpectrumLayerPreview>,
): WebGpuSpectrumGradientAtlas {
  const width = SPECTRUM_GRADIENT_ATLAS_WIDTH
  const height = Math.max(1, layers.length)
  const rgba = new Uint8Array(width * height * 4)

  for (let rowIndex = 0; rowIndex < height; rowIndex += 1) {
    const colors = layers[rowIndex]?.colors?.length ? layers[rowIndex].colors : ['#ffffff']
    for (let columnIndex = 0; columnIndex < width; columnIndex += 1) {
      const sample = sampleGradientPaletteColor(colors, columnIndex / Math.max(1, width - 1))
      const offset = (rowIndex * width + columnIndex) * 4
      rgba[offset] = Math.round(clamp(sample.red, 0, 1) * 255)
      rgba[offset + 1] = Math.round(clamp(sample.green, 0, 1) * 255)
      rgba[offset + 2] = Math.round(clamp(sample.blue, 0, 1) * 255)
      rgba[offset + 3] = 255
    }
  }

  return {
    width,
    height,
    rgba,
  }
}

function resolveSpectrumVariant(layer: SpectrumLayerPreview, styleFamily: string): number {
  if (styleFamily === 'straight-bars') {
    return 6
  }
  if (styleFamily === 'dot-matrix' || styleFamily === 'pixel-bars') {
    return 1
  }
  if (
    styleFamily === 'soft-waveform' ||
    styleFamily === 'continuous-waveform' ||
    styleFamily === 'wave-ribbon'
  ) {
    return 2
  }
  if (
    layer.fillCircle ||
    styleFamily === 'mountain' ||
    styleFamily === 'liquid' ||
    styleFamily === 'liquid-mass'
  ) {
    return 3
  }
  if (styleFamily === 'flying-glow' || styleFamily === 'floating-blocks') {
    return 4
  }
  if (styleFamily === 'halo-stack') {
    return 5
  }
  return 0
}

function buildSpectrumRenderPasses(
  layer: SpectrumLayerPreview,
  styleFamily: string,
): SpectrumRenderPass[] {
  const glowStrength = clamp(layer.glow / 100, 0, 1.2)
  const glowSoftness = clamp(layer.blur, 0, 30)
  const opacity = clamp(layer.opacity, 0, 1)
  const passes: SpectrumRenderPass[] = []
  const luminousLayer = layer.blendMode === 'screen' || layer.blendMode === 'add'
  const flyingGlowStyle = styleFamily === 'flying-glow'
  const straightStyle = styleFamily === 'straight-bars'
  const haloStyle = styleFamily === 'halo-stack'
  const waveStyle =
    styleFamily === 'soft-waveform' ||
    styleFamily === 'continuous-waveform' ||
    styleFamily === 'wave-ribbon'
  const massStyle =
    styleFamily === 'mountain' || styleFamily === 'liquid' || styleFamily === 'liquid-mass'

  if (flyingGlowStyle) {
    passes.push({
      isGlow: false,
      foundationRing: true,
      alpha: clamp(opacity * 0.96, 0.72, 1),
      barWidth: layer.barWidth + 0.4,
      thickness: layer.thickness * 0.74,
      solidBand: true,
      fillCircle: false,
      glow: 0,
      blur: Math.min(layer.blur, 0.2),
      blendMode: 'opaque',
    })
    if (glowStrength > 0.04) {
      passes.push({
        isGlow: true,
        alpha: clamp(opacity * (0.014 + glowStrength * 0.028), 0.008, 0.055),
        barWidth: layer.barWidth + (glowSoftness * 0.02 + glowStrength * 0.14),
        thickness: layer.thickness + (glowSoftness * 0.03 + glowStrength * 1.9),
        solidBand: true,
        fillCircle: false,
        glow: layer.glow + glowStrength * 4,
        blur: layer.blur + glowSoftness * 0.02 + glowStrength * 0.22,
        blendMode: 'screen',
      })
    }
    if (glowStrength > 0.3) {
      passes.push({
        isGlow: true,
        alpha: clamp(opacity * (0.004 + glowStrength * 0.012), 0.004, 0.022),
        barWidth: layer.barWidth + (glowSoftness * 0.04 + glowStrength * 0.24),
        thickness: layer.thickness + (glowSoftness * 0.05 + glowStrength * 2.8),
        solidBand: true,
        fillCircle: false,
        glow: layer.glow + glowStrength * 8,
        blur: layer.blur + glowSoftness * 0.05 + glowStrength * 0.42,
        blendMode: 'add',
      })
    }
  } else if (straightStyle) {
    if (glowStrength > 0.04) {
      passes.push({
        isGlow: true,
        alpha: clamp(opacity * (0.045 + glowStrength * 0.06), 0.025, 0.14),
        barWidth: layer.barWidth + (glowSoftness * 0.05 + glowStrength * 0.24),
        thickness: layer.thickness + (glowSoftness * 0.08 + glowStrength * 4.5),
        solidBand: layer.solidBand,
        fillCircle: false,
        glow: layer.glow + glowStrength * 10,
        blur: layer.blur + glowSoftness * 0.12 + glowStrength * 0.8,
        blendMode: 'screen',
      })
    }
    if (glowStrength > 0.28 || luminousLayer) {
      passes.push({
        isGlow: true,
        alpha: clamp(opacity * (0.012 + glowStrength * 0.028), 0.01, 0.055),
        barWidth: layer.barWidth + (glowSoftness * 0.08 + glowStrength * 0.42),
        thickness: layer.thickness + (glowSoftness * 0.12 + glowStrength * 6),
        solidBand: layer.solidBand,
        fillCircle: false,
        glow: layer.glow + glowStrength * 18,
        blur: layer.blur + glowSoftness * 0.18 + glowStrength * 1.4,
        blendMode: 'add',
      })
    }
  } else if (haloStyle) {
    passes.push({
      isGlow: true,
      alpha: clamp(opacity * (0.12 + glowStrength * 0.16), 0.06, 0.28),
      barWidth: layer.barWidth + (glowSoftness * 0.1 + glowStrength * 0.85),
      thickness: layer.thickness + (glowSoftness * 0.14 + glowStrength * 8),
      solidBand: layer.solidBand,
      fillCircle: false,
      glow: layer.glow + glowStrength * 28,
      blur: layer.blur + glowSoftness * 0.28 + glowStrength * 2.5,
      blendMode: 'screen',
    })
    passes.push({
      isGlow: true,
      alpha: clamp(opacity * (0.05 + glowStrength * 0.08), 0.02, 0.18),
      barWidth: layer.barWidth + (glowSoftness * 0.22 + glowStrength * 1.9),
      thickness: layer.thickness + (glowSoftness * 0.22 + glowStrength * 14),
      solidBand: layer.solidBand,
      fillCircle: false,
      glow: layer.glow + glowStrength * 46,
      blur: layer.blur + glowSoftness * 0.55 + glowStrength * 5,
      blendMode: 'add',
    })
  } else {
    if (glowStrength > 0.08) {
      passes.push({
        isGlow: true,
        alpha: clamp(
          opacity *
            (waveStyle
              ? 0.07 + glowStrength * 0.11
              : massStyle
                ? 0.06 + glowStrength * 0.09
                : 0.08 + glowStrength * 0.14),
          0.03,
          waveStyle ? 0.24 : 0.34,
        ),
        barWidth:
          layer.barWidth +
          (waveStyle
            ? glowSoftness * 0.08 + glowStrength * 0.6
            : massStyle
              ? glowSoftness * 0.09 + glowStrength * 0.7
              : glowSoftness * 0.12 + glowStrength * 0.9),
        thickness:
          layer.thickness +
          (waveStyle
            ? glowSoftness * 0.1 + glowStrength * 6
            : massStyle
              ? glowSoftness * 0.12 + glowStrength * 8
              : glowSoftness * 0.16 + glowStrength * 10),
        solidBand: layer.solidBand,
        fillCircle: false,
        glow:
          layer.glow + (waveStyle ? glowStrength * 20 : massStyle ? glowStrength * 18 : glowStrength * 42),
        blur:
          layer.blur +
          (waveStyle
            ? glowSoftness * 0.22 + glowStrength * 1.6
            : massStyle
              ? glowSoftness * 0.18 + glowStrength * 1.4
              : glowSoftness * 0.45 + glowStrength * 4),
        blendMode: luminousLayer ? 'screen' : 'add',
      })
    }
    if (glowStrength > 0.55 || luminousLayer) {
      passes.push({
        isGlow: true,
        alpha: clamp(
          opacity * (massStyle ? 0.035 + glowStrength * 0.06 : 0.05 + glowStrength * 0.1),
          0.02,
          massStyle ? 0.14 : 0.22,
        ),
        barWidth:
          layer.barWidth +
          (waveStyle
            ? glowSoftness * 0.12 + glowStrength * 1.0
            : massStyle
              ? glowSoftness * 0.16 + glowStrength * 1.2
              : glowSoftness * 0.18 + glowStrength * 1.6),
        thickness:
          layer.thickness +
          (waveStyle
            ? glowSoftness * 0.18 + glowStrength * 10
            : massStyle
              ? glowSoftness * 0.18 + glowStrength * 11
              : glowSoftness * 0.24 + glowStrength * 15),
        solidBand: layer.solidBand,
        fillCircle: false,
        glow:
          layer.glow + (waveStyle ? glowStrength * 32 : massStyle ? glowStrength * 28 : glowStrength * 58),
        blur:
          layer.blur +
          (waveStyle
            ? glowSoftness * 0.36 + glowStrength * 3.2
            : massStyle
              ? glowSoftness * 0.3 + glowStrength * 2.4
              : glowSoftness * 0.62 + glowStrength * 7),
        blendMode: 'add',
      })
    }
  }

  passes.push({
    isGlow: false,
    alpha: opacity,
    barWidth: layer.barWidth,
    thickness: layer.thickness,
    solidBand: layer.solidBand,
    fillCircle: layer.fillCircle,
    glow: layer.glow,
    blur: flyingGlowStyle ? Math.min(layer.blur, 0.45) : layer.blur,
    blendMode: flyingGlowStyle ? 'normal' : layer.blendMode,
  })

  return passes
}

function buildSpectrumPassLayer(
  layer: SpectrumLayerPreview,
  pass: SpectrumRenderPass,
): SpectrumLayerPreview {
  return {
    ...layer,
    opacity: pass.alpha,
    barWidth: pass.barWidth,
    thickness: pass.thickness,
    solidBand: pass.solidBand,
    fillCircle: pass.fillCircle,
    glow: pass.glow,
    blur: pass.blur,
    blendMode: pass.blendMode,
  }
}

function resolveSpectrumGravityAngle(gravity: string): number {
  switch (gravity) {
    case 'top':
      return Math.PI / 2
    case 'left':
      return 0
    case 'right':
      return Math.PI
    case 'bottom':
    default:
      return -Math.PI / 2
  }
}

function resolveFlyingGlowSourceAngle(gravity: string): number {
  switch (String(gravity || 'bottom').trim().toLowerCase()) {
    case 'top':
      return -Math.PI / 2
    case 'left':
      return Math.PI
    case 'right':
      return 0
    case 'bottom':
    default:
      return Math.PI / 2
  }
}

function resolveSpectrumArc(layer: SpectrumLayerPreview, progress: number): number {
  const centerAngle = resolveSpectrumGravityAngle(layer.gravity)
  if (layer.mirrored) {
    return centerAngle - Math.PI + progress * Math.PI * 2
  }
  return centerAngle - Math.PI / 2 + progress * Math.PI
}

function resolveFlyingWingProfile(
  layer: SpectrumLayerPreview,
  progress: number,
): FlyingWingProfile {
  if (layer.curved) {
    const angle = resolveSpectrumArc(layer, progress)
    const sourceAngle = resolveFlyingGlowSourceAngle(layer.gravity)
    const targetAngle = wrapAngleToPi(sourceAngle + Math.PI)
    const relativeTopAngle = wrapAngleToPi(angle - targetAngle)
    const travelBias = (1 - Math.cos(wrapAngleToPi(angle - sourceAngle))) * 0.5
    const travelLift = 0.34 + travelBias * 0.66
    const rightShoulder = sampleBellCurve(relativeTopAngle, 0.82, 0.34)
    const leftShoulder = sampleBellCurve(relativeTopAngle, -0.82, 0.34)
    const shoulderBias = Math.max(leftShoulder, rightShoulder)
    const shoulderBed = Math.max(
      sampleBellCurve(relativeTopAngle, -0.82, 0.68),
      sampleBellCurve(relativeTopAngle, 0.82, 0.68),
    )
    const centerDip = sampleBellCurve(relativeTopAngle, 0, 0.28)
    const topFocus = Math.pow(clamp((Math.cos(relativeTopAngle) + 1) * 0.5, 0, 1), 1.8)

    return {
      shoulderBias,
      centerDip,
      topFocus,
      lengthBias: clamp(
        0.16 + topFocus * 0.24 + shoulderBias * 0.96 + shoulderBed * 0.22 - centerDip * topFocus * 0.28,
        0.05,
        1.35,
      ),
      widthBias: clamp(0.2 + shoulderBias * 0.62 + topFocus * 0.14 - centerDip * 0.08, 0.1, 1.1),
      glowBias: clamp(0.24 + shoulderBias * 0.72 + topFocus * 0.2 - centerDip * 0.04, 0.12, 1.3),
      travelBias,
      travelLift,
    }
  }

  const shoulderBias = Math.max(
    sampleBellCurve(progress, 0.18, 0.14),
    sampleBellCurve(progress, 0.82, 0.14),
  )
  const shoulderBed = Math.max(
    sampleBellCurve(progress, 0.18, 0.24),
    sampleBellCurve(progress, 0.82, 0.24),
  )
  const centerDip = sampleBellCurve(progress, 0.5, 0.16)

  return {
    shoulderBias,
    centerDip,
    topFocus: 1,
    lengthBias: clamp(0.18 + shoulderBias * 0.92 + shoulderBed * 0.24 - centerDip * 0.24, 0.08, 1.28),
    widthBias: clamp(0.2 + shoulderBias * 0.56 - centerDip * 0.1, 0.1, 0.96),
    glowBias: clamp(0.26 + shoulderBias * 0.68 - centerDip * 0.06, 0.14, 1.08),
    travelBias: progress,
    travelLift: 0.34 + progress * 0.66,
  }
}

function resolveSpectrumLinearGeometry(
  layer: SpectrumLayerPreview,
  progress: number,
  centerX: number,
  centerY: number,
): SpectrumSampleGeometry {
  const gravity = String(layer.gravity || 'bottom').trim().toLowerCase()
  const totalLength =
    gravity === 'left' || gravity === 'right'
      ? Math.max(48, centerY * 2 * 0.8)
      : Math.max(48, centerX * 2 * 0.8)
  const offset = -totalLength * 0.5 + progress * totalLength

  switch (gravity) {
    case 'top':
      return {
        baseX: centerX + offset,
        baseY: centerY,
        dirX: 0,
        dirY: 1,
      }
    case 'left':
      return {
        baseX: centerX,
        baseY: centerY + offset,
        dirX: 1,
        dirY: 0,
      }
    case 'right':
      return {
        baseX: centerX,
        baseY: centerY + offset,
        dirX: -1,
        dirY: 0,
      }
    case 'bottom':
    default:
      return {
        baseX: centerX + offset,
        baseY: centerY,
        dirX: 0,
        dirY: -1,
      }
  }
}

function resolveSpectrumSampleGeometry(
  layer: SpectrumLayerPreview,
  progress: number,
  centerX: number,
  centerY: number,
  radiusBase: number,
): SpectrumSampleGeometry {
  if (!layer.curved) {
    return resolveSpectrumLinearGeometry(layer, progress, centerX, centerY)
  }

  const angle = resolveSpectrumArc(layer, progress)
  const dirX = Math.cos(angle)
  const dirY = Math.sin(angle)
  return {
    baseX: centerX + dirX * radiusBase,
    baseY: centerY + dirY * radiusBase,
    dirX,
    dirY,
  }
}

function resolveAdjacentSampleSpacing(
  layer: SpectrumLayerPreview,
  index: number,
  valueCount: number,
  centerX: number,
  centerY: number,
  radiusBase: number,
): number {
  if (valueCount <= 1) {
    return 0
  }

  const currentProgress = index / Math.max(1, valueCount)
  const nextProgress = Math.min(valueCount - 1, index + 1) / Math.max(1, valueCount)
  const previousProgress = Math.max(0, index - 1) / Math.max(1, valueCount)
  const current = resolveSpectrumSampleGeometry(layer, currentProgress, centerX, centerY, radiusBase)
  const next = resolveSpectrumSampleGeometry(layer, nextProgress, centerX, centerY, radiusBase)
  const previous = resolveSpectrumSampleGeometry(layer, previousProgress, centerX, centerY, radiusBase)
  const nextDistance = Math.hypot(next.baseX - current.baseX, next.baseY - current.baseY)
  const previousDistance = Math.hypot(current.baseX - previous.baseX, current.baseY - previous.baseY)
  return Math.max(nextDistance, previousDistance)
}

function normalizeWebGpuSpectrumStyle(styleKey: string): string {
  switch (normalizeSpectrumStyleKey(styleKey)) {
    case 'classic-vertical':
    case 'straight-bars':
    case 'symmetrical-bars':
    case 'pixel-bars':
    case 'floating-blocks':
    case 'neon-pulse':
    case 'thin-lines':
      return normalizeSpectrumStyleKey(styleKey)
    case 'dot-matrix':
      return 'pixel-bars'
    case 'flying-glow':
    case 'halo-stack':
    case 'soft-waveform':
    case 'continuous-waveform':
    case 'wave-ribbon':
    case 'mountain':
    case 'liquid':
    case 'liquid-mass':
      return 'straight-bars'
    default:
      return 'straight-bars'
  }
}

export function buildWebGpuSpectrumInstances(
  centerX: number,
  centerY: number,
  radiusBase: number,
  layer: SpectrumLayerPreview,
  values: number[],
  reactiveEnergy: number,
  scale: number,
  styleMotionDrive?: number,
  options?: {
    gradientV?: number
    heightScale?: number
  },
): WebGpuSpectrumInstance[] {
  const instances: WebGpuSpectrumInstance[] = []
  const baseStyleFamily = normalizeSpectrumStyleKey(layer.styleKey)
  const passSpecs = buildSpectrumRenderPasses(layer, baseStyleFamily)
  const gradientV = clamp(options?.gradientV ?? 0.5, 0, 1)
  const heightScale = clamp(options?.heightScale ?? 1, 0.5, 6)

  passSpecs.forEach((passSpec) => {
    const passLayer = buildSpectrumPassLayer(layer, passSpec)
    const foundationRing = Boolean(passSpec.foundationRing)
    const normalizedStyle = normalizeWebGpuSpectrumStyle(passLayer.styleKey)
    const pixelBars = normalizedStyle === 'pixel-bars'
    const neonPulse = normalizedStyle === 'neon-pulse'
    const thinLines = normalizedStyle === 'thin-lines'
    const symmetricalBars = normalizedStyle === 'symmetrical-bars'
    const floatingBlocks = normalizedStyle === 'floating-blocks'
    const styleFamily = normalizeSpectrumStyleKey(passLayer.styleKey)
    const flyingGlowStyle = styleFamily === 'flying-glow'
    const wingStyle = flyingGlowStyle || styleFamily === 'halo-stack'
    const straightStyle = styleFamily === 'straight-bars'
    const haloStyle = styleFamily === 'halo-stack'
    const waveStyle =
      styleFamily === 'soft-waveform' ||
      styleFamily === 'continuous-waveform' ||
      styleFamily === 'wave-ribbon'
    const massStyle =
      styleFamily === 'mountain' || styleFamily === 'liquid' || styleFamily === 'liquid-mass'
    const renderValues = flyingGlowStyle ? buildFlyingGlowContinuousValues(values) : values
    const solidWingBand = flyingGlowStyle || (styleFamily === 'halo-stack' && passLayer.solidBand)
    const geometryValues =
      flyingGlowStyle && passLayer.solidBand
        ? smoothCircularValuesStrong(renderValues).map((smoothed, index) =>
            clamp(smoothed * 0.9 + (renderValues[index] ?? 0) * 0.1, 0, 1),
          )
        : flyingGlowStyle
          ? smoothCircularValues(renderValues).map((smoothed, index) =>
              clamp(smoothed * 0.86 + (renderValues[index] ?? 0) * 0.14, 0, 1),
            )
          : renderValues
    const averageValue = geometryValues.length
      ? geometryValues.reduce((sum, current) => sum + current, 0) / geometryValues.length
      : 0
    const barLengthScale =
      passLayer.thickness *
      scale *
      (straightStyle ? 0.82 : wingStyle ? 0.68 : waveStyle ? 0.72 : massStyle ? 0.7 : 0.74) *
      heightScale

    renderValues.forEach((value, index) => {
      const geometryValue = geometryValues[index] ?? value
      const progress = index / Math.max(1, renderValues.length)
      const sample = resolveSpectrumSampleGeometry(passLayer, progress, centerX, centerY, radiusBase)
      const dirX = sample.dirX
      const dirY = sample.dirY
      const steppedLength = pixelBars ? Math.max(6 * scale, barLengthScale * 0.18) : 0
      const centerBias = 1 - Math.abs(progress - 0.5) / 0.5
      const wingProfile = wingStyle ? resolveFlyingWingProfile(passLayer, progress) : null
      const travelLift = wingProfile?.travelLift ?? (0.34 + progress * 0.66)
      const variant = resolveSpectrumVariant(passLayer, styleFamily)
      const gradientU = flyingGlowStyle
        ? resolveFlyingGlowGradientSampleProgress(
            passLayer,
            progress,
            sample,
            centerX,
            centerY,
            radiusBase,
          )
        : foundationRing
          ? clamp(progress, 0, 1)
          : resolveGradientSampleProgress(passLayer, progress, value, centerBias)
      const fallbackColor = sampleGradientPaletteColor(passLayer.colors, gradientU)

      let barLength = thinLines
        ? barLengthScale * (0.25 + value * 0.95)
        : barLengthScale * (0.3 + value * (neonPulse ? 1.14 : 1.05))
      if (wingStyle) {
        const wingValue = Math.pow(geometryValue, flyingGlowStyle ? 0.88 : 0.84)
        const energyDrive = clamp(reactiveEnergy, 0, 1)
        const motionDrive = clamp(styleMotionDrive ?? reactiveEnergy, 0, 1)
        const wingBlend = flyingGlowStyle ? smoothstep01((motionDrive - 0.14) / 0.5) : 1
        const restRing = foundationRing
          ? 0.11 + energyDrive * (0.012 + travelLift * 0.048)
          : flyingGlowStyle
            ? 0.04 + energyDrive * (0.016 + travelLift * 0.034)
            : 0.28
        const ringBedValue = flyingGlowStyle
          ? clamp(averageValue * 0.78 + wingValue * 0.22, 0, 1)
          : wingValue
        const circularBreath = foundationRing
          ? clamp(averageValue, 0, 1) * (0.08 + energyDrive * (0.08 + travelLift * 0.14))
          : flyingGlowStyle
          ? ringBedValue *
              (0.14 + travelLift * 0.2 + energyDrive * (0.1 + travelLift * 0.09)) *
              (1 - wingBlend * 0.08)
          : wingValue * (0.17 + energyDrive * 0.03)
        const flareDrive = foundationRing
          ? 0
          : flyingGlowStyle
            ? wingBlend * Math.pow(motionDrive, 1.42)
            : Math.pow(energyDrive, 1.18)
        const wingFlare =
          flareDrive *
          Math.pow(Math.max(flyingGlowStyle ? 0.035 : 0, wingValue), flyingGlowStyle ? 0.82 : 0.78) *
          (0.02 +
            travelLift * (flyingGlowStyle ? 0.18 : 0.05) +
            (wingProfile?.shoulderBias ?? 0) * (flyingGlowStyle ? 1.14 : 0.76) +
            (wingProfile?.topFocus ?? 1) * (flyingGlowStyle ? 0.12 : 0.05) -
            (wingProfile?.centerDip ?? 0) * (flyingGlowStyle ? 0.16 : 0.02))
        barLength = barLengthScale * (restRing + circularBreath + wingFlare)
      } else if (straightStyle) {
        barLength = barLengthScale * (0.08 + reactiveEnergy * 0.18 + Math.pow(value, 0.76) * 1.34)
      } else if (waveStyle) {
        barLength = barLengthScale * (0.18 + reactiveEnergy * 0.15 + value * 0.86)
      } else if (massStyle) {
        barLength = barLengthScale * (0.34 + reactiveEnergy * 0.12 + value * 1.02)
      }
      if (pixelBars && steppedLength > 0) {
        barLength = Math.ceil(barLength / steppedLength) * steppedLength
      }

      let halfWidth = Math.max(
        thinLines ? Math.max(scale * 0.4, passLayer.barWidth * scale * 0.24) : straightStyle ? 1 : 2,
        passLayer.barWidth * scale * (thinLines ? 0.24 : neonPulse ? 0.57 : 0.5),
      )
      if (passLayer.solidBand || flyingGlowStyle) {
        const adjacentSpacing = resolveAdjacentSampleSpacing(
          passLayer,
          index,
          renderValues.length,
          centerX,
          centerY,
          radiusBase,
        )
        halfWidth = Math.max(
          halfWidth,
          adjacentSpacing *
            (foundationRing
              ? 1.08
              : flyingGlowStyle
                ? passLayer.solidBand
                  ? 0.96
                  : 0.82
                : wingStyle
                  ? 0.82
                  : 0.56),
        )
      }
      if (wingStyle) {
        halfWidth = Math.max(
          halfWidth,
          passLayer.barWidth *
            scale *
            (foundationRing
              ? 0.66
              : flyingGlowStyle
              ? 0.42 +
                (wingProfile?.widthBias ?? 0.4) *
                  (0.08 +
                    smoothstep01((clamp(styleMotionDrive ?? reactiveEnergy, 0, 1) - 0.14) / 0.5) * 0.5)
              : 0.52 + (wingProfile?.widthBias ?? 0.4) * 0.58),
        )
      } else if (massStyle) {
        halfWidth = Math.max(halfWidth, passLayer.barWidth * scale * 0.72)
      }
      let baseOffset = 0
      let effectiveLength = barLength

      if (symmetricalBars) {
        baseOffset = -effectiveLength * 0.5
      }

      if (floatingBlocks) {
        baseOffset = effectiveLength + 20 * scale
        effectiveLength = 10 * scale
      }

      if (variant === 1) {
        baseOffset = passLayer.curved ? baseOffset : baseOffset - effectiveLength * 0.12
        effectiveLength = Math.max(halfWidth * 1.8, 8 * scale + value * 20 * scale)
        halfWidth = Math.max(halfWidth, effectiveLength * 0.42)
      } else if (variant === 6) {
        effectiveLength *= 1.02 + value * 0.08
        halfWidth = Math.max(
          straightStyle ? 1 : 2,
          Math.max(halfWidth, passLayer.barWidth * scale * 0.42),
        )
        baseOffset -= effectiveLength * 0.02
      } else if (variant === 2) {
        effectiveLength *= 0.88 + centerBias * 0.08
        halfWidth = Math.max(halfWidth, passLayer.barWidth * scale * (1.06 + reactiveEnergy * 0.08))
        baseOffset -= effectiveLength * (0.18 + centerBias * 0.06)
      } else if (variant === 3) {
        effectiveLength *= 1.12 + value * 0.05
        halfWidth = Math.max(halfWidth, passLayer.barWidth * scale * (1.18 + reactiveEnergy * 0.06))
        baseOffset -= effectiveLength * 0.24
      } else if (variant === 4) {
        if (foundationRing) {
          baseOffset -= effectiveLength * 0.5
        }
        const motionDrive = clamp(styleMotionDrive ?? reactiveEnergy, 0, 1)
        const wingBlend = flyingGlowStyle ? smoothstep01((motionDrive - 0.14) / 0.5) : 1
        const travelBias = wingProfile?.travelBias ?? progress
        const wingDynamicBias =
          foundationRing
            ? 0
            : Math.pow(
            flyingGlowStyle ? motionDrive : clamp(reactiveEnergy, 0, 1),
            flyingGlowStyle ? 1.62 : 1.24,
          ) *
              (0.03 +
                (wingProfile?.shoulderBias ?? 0) * (flyingGlowStyle ? 0.3 : 0.24) +
                (wingProfile?.topFocus ?? 1) * (flyingGlowStyle ? 0.06 : 0.04)) *
              (0.46 + travelBias * 0.3 + geometryValue * 0.24) *
              wingBlend
        effectiveLength *= 1 + wingDynamicBias
        halfWidth = Math.max(
          halfWidth,
          passLayer.barWidth * scale * (foundationRing ? 0.72 : flyingGlowStyle ? 0.52 : 0.62) +
            passLayer.barWidth *
              scale *
              ((wingProfile?.widthBias ?? centerBias) * (foundationRing ? 0.05 : flyingGlowStyle ? 0.14 : 0.22) +
                travelLift * (foundationRing ? 0.08 : flyingGlowStyle ? 0.08 : 0) +
                wingDynamicBias * (flyingGlowStyle ? 0.12 : 0.18)),
        )
        baseOffset -=
          effectiveLength *
          (foundationRing
            ? 0
            : flyingGlowStyle
              ? 0.022 + wingDynamicBias * 0.07
              : 0.015 + wingDynamicBias * 0.06)
      } else if (variant === 5) {
        effectiveLength *= 1.12 + centerBias * 0.2
        halfWidth = Math.max(halfWidth, passLayer.barWidth * scale * (0.82 + centerBias * 0.28))
        baseOffset -= effectiveLength * 0.1
      }

      if (neonPulse) {
        const pulse = 1 + reactiveEnergy * 0.3
        effectiveLength *= pulse
        halfWidth *= 1.25
      }

      const baseX = sample.baseX + dirX * baseOffset
      const baseY = sample.baseY + dirY * baseOffset

      instances.push({
        baseX,
        baseY,
        dirX,
        dirY,
        halfWidth,
        length: Math.max(scale, effectiveLength),
        red: fallbackColor.red,
        green: fallbackColor.green,
        blue: fallbackColor.blue,
        alpha: clamp(
          passLayer.opacity *
            (straightStyle
              ? 0.34 + centerBias * 0.08 + Math.pow(value, 0.82) * 0.82
              : haloStyle
                ? 0.46 + centerBias * 0.3 + value * 0.62
                : wingStyle
                  ? flyingGlowStyle
                    ? foundationRing
                      ? 0.82 + travelLift * 0.16
                      : passSpec.isGlow
                      ? 0.18 +
                        travelLift * 0.12 +
                        (wingProfile?.glowBias ?? 0.5) *
                          (0.08 +
                            smoothstep01((clamp(styleMotionDrive ?? reactiveEnergy, 0, 1) - 0.14) / 0.5) *
                              0.14) +
                        (averageValue * 0.78 + geometryValue * 0.22) * 0.58 +
                        clamp(styleMotionDrive ?? reactiveEnergy, 0, 1) * 0.12
                      : 0.54 +
                        travelLift * 0.16 +
                        (wingProfile?.glowBias ?? 0.5) *
                          (0.06 +
                            smoothstep01((clamp(styleMotionDrive ?? reactiveEnergy, 0, 1) - 0.14) / 0.5) *
                              0.08) +
                        (averageValue * 0.72 + geometryValue * 0.28) * 0.34 +
                        clamp(styleMotionDrive ?? reactiveEnergy, 0, 1) * 0.08
                    : 0.28 + (wingProfile?.glowBias ?? 0.5) * 0.26 + value * 0.7
                  : waveStyle
                    ? 0.32 + centerBias * 0.18 + value * 0.6
                    : thinLines
                      ? 0.42 + value * 0.75
                      : neonPulse
                        ? 0.52 + value * 0.92
                        : massStyle
                          ? 0.44 + value * 0.78
                          : 0.4 + value * 0.85),
          0.08,
          1,
        ),
        softness: flyingGlowStyle
          ? clamp(
              0.008 +
                (passLayer.blur * 0.1 + passLayer.glow * 0.006) / 120 +
                (passSpec.isGlow ? 0.008 : 0),
              passSpec.isGlow ? 0.008 : 0.004,
              passSpec.isGlow ? 0.032 : 0.014,
            )
          : clamp(
              0.04 +
                ((solidWingBand ? passLayer.blur * 0.58 : passLayer.blur) + passLayer.glow * 0.032) / 120 +
                (straightStyle
                  ? -0.008
                  : haloStyle
                    ? 0.04
                    : wingStyle
                      ? solidWingBand
                        ? 0.004
                        : 0.03
                      : waveStyle
                        ? 0.015
                        : massStyle
                          ? 0.01
                          : 0),
              straightStyle ? 0.03 : solidWingBand ? 0.028 : 0.035,
              straightStyle ? 0.11 : solidWingBand ? 0.1 : haloStyle ? 0.2 : waveStyle ? 0.18 : 0.22,
            ),
        glow: clamp(
          (passLayer.glow + passLayer.blur * 1.1) / 132 +
            (straightStyle
              ? 0.035 + Math.pow(value, 1.18) * 0.16
              : haloStyle
                ? 0.34
                : wingStyle
                  ? 0.14 + (wingProfile?.glowBias ?? 0.4) * 0.16 + Math.pow(value, 0.92) * 0.08
                  : waveStyle
                    ? 0.08
                    : massStyle
                      ? 0.12
                      : 0),
          0.05,
          straightStyle ? 0.72 : haloStyle ? 2.1 : 1.85,
        ),
        variant,
        blendMode: passLayer.blendMode,
        gradientU,
        gradientV,
      })
    })
  })

  return instances
}
