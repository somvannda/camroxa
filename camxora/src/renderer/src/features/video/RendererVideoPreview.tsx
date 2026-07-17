import { useEffect, useMemo } from 'react'

import type {
  TemplateTextOverlayDraft,
  VideoTemplateDraft,
} from '@/features/video/core/contracts/videoTemplateDraft'
import { buildVideoTemplateDraft } from '@/features/video/core/contracts/videoTemplateDraft'
import {
  resolveBackgroundPresentationState,
  type BackgroundPresentationState,
} from '@/features/video/domains/background/backgroundPreviewRuntime'
import {
  resolveLogoPresentationState,
  type LogoPresentationState,
} from '@/features/video/domains/logo/logoPreviewRuntime'
import type { PreviewLogoDrawDraft } from '@/features/video/core/contracts/previewDraftContracts'
import {
  buildLayerSpectrumValues,
  buildSyntheticSpectrumValues,
  resolveSpectrumBarCount,
  smoothPreviewReactiveValue,
  updateFlyingGlowWingEnvelope,
} from '@/features/video/domains/spectrum/spectrumPreviewRuntime'
import { normalizeSpectrumStyleKey } from '@/features/video/domains/spectrum/spectrumLayerModel'
import { PreviewProvider } from '@/features/video/preview/PreviewProvider'
import type {
  PreviewManualRenderFrameOptions,
  PreviewProviderRenderState,
} from '@/features/video/preview/previewProviderContract'
import { RendererVideoPreviewSurface } from '@/features/video/preview/RendererVideoPreviewSurface'
import {
  type PreviewLifecycleState,
} from '@/features/video/preview/previewLifecycleState'
import {
  type PreviewPlaybackCommand,
} from '@/features/video/preview/transportClock'
import type { VideoWorkspaceState } from '@/shared/types/desktop'

export {
  resolveBackgroundPresentationState,
  resolveBackgroundReactiveDriveEnergy,
} from '@/features/video/domains/background/backgroundPreviewRuntime'
export {
  resolveLogoPresentationState,
  resolveLogoReactiveDriveEnergy,
} from '@/features/video/domains/logo/logoPreviewRuntime'

type RendererVideoPreviewProps = {
  template: Record<string, unknown>
  workspace: Pick<VideoWorkspaceState, 'previewAspectRatio' | 'playback'>
  templateDraft: VideoTemplateDraft | null
  backgroundPath: string
  logoPath: string
  selectedMp3Path: string
  previewVolume: number
  selectedTextOverlayIndex: number
  playbackCommand: PreviewPlaybackCommand | null
  onPlaybackStateChange?: (state: VideoWorkspaceState['playback']) => void
  onLifecycleStateChange?: (state: PreviewLifecycleState) => void
  onManualRenderFrameReady?: (renderFrame: ((options: PreviewManualRenderFrameOptions) => void) | null) => void
  onReadbackFrameCaptureReady?: (captureFrame: (() => Promise<Uint8Array | null>) | null) => void
  runtimeMode?: 'live' | 'manual-export'
  enableSpectrumPositionEditing?: boolean
  onSpectrumPositionChange?: (patch: {
    anchor: string
    positionX: number
    positionY: number
    spectrumAttachToLogo: boolean
  }) => void
}

type SpectrumLogBinMapping = {
  idx1: Int32Array
  idx2: Int32Array
  frac: Float32Array
}

export type SpectrumReactiveEnvelope = {
  bassFast: number
  bassSlow: number
  kick: number
  drop: number
  level: number
  bins: Float32Array | null
  floorBins: Float32Array | null
  styleKey: string
}


type AnalysedSpectrumFrame = {
  smoothedValues: Float32Array
  reactiveEnergy: number
}

type SpectrumAnalysisProfile = {
  smoothing: 'smooth' | 'crisp'
  attackSec: number
  releaseSec: number
  floorSec: number
  floorMix: number
  localAccentBase: number
  localAccentLift: number
  meanLift: number
  tailTrim: number
  floorWeight: number
  minFloor: number
  maxFloor: number
  accentStrength: number
  curveExp: number
}

type RendererVideoPreviewSurfaceBridgeProps = {
  previewState: PreviewProviderRenderState<ResolvedTextOverlayPreview>
  enableSpectrumPositionEditing?: boolean
  onLifecycleStateChange?: (state: PreviewLifecycleState) => void
  onManualRenderFrameReady?: (renderFrame: ((options: PreviewManualRenderFrameOptions) => void) | null) => void
  onReadbackFrameCaptureReady?: (captureFrame: (() => Promise<Uint8Array | null>) | null) => void
  onSpectrumPositionChange?: (patch: {
    anchor: string
    positionX: number
    positionY: number
    spectrumAttachToLogo: boolean
  }) => void
}

function RendererVideoPreviewSurfaceBridge({
  previewState,
  enableSpectrumPositionEditing,
  onLifecycleStateChange,
  onManualRenderFrameReady,
  onReadbackFrameCaptureReady,
  onSpectrumPositionChange,
}: RendererVideoPreviewSurfaceBridgeProps): React.JSX.Element {
  useEffect(() => {
    onManualRenderFrameReady?.(previewState.manualRenderFrame)
    return () => {
      onManualRenderFrameReady?.(null)
    }
  }, [onManualRenderFrameReady, previewState.manualRenderFrame])

  useEffect(() => {
    const renderer = previewState.webgpuRendererRef.current
    if (!renderer || !onReadbackFrameCaptureReady) {
      onReadbackFrameCaptureReady?.(null)
      return
    }
    renderer.setReadbackEnabled(true)
    onReadbackFrameCaptureReady(() => renderer.readbackLatestFrame())
    return () => {
      renderer.setReadbackEnabled(false)
      onReadbackFrameCaptureReady(null)
    }
  }, [onReadbackFrameCaptureReady, previewState.webgpuRendererRef])

  return (
    <RendererVideoPreviewSurface
      {...previewState}
      enableSpectrumPositionEditing={enableSpectrumPositionEditing}
      onLifecycleStateChange={onLifecycleStateChange}
      onSpectrumPositionChange={onSpectrumPositionChange}
    />
  )
}

type ResolvedTextOverlayPreview = {
  key: string
  index: number
  text: string
  anchor: string
  offsetX: number
  offsetY: number
  textScale: number
  opacity: number
  textAlign: CanvasTextAlign
  fontSizePx: number
  strokeWidthPx: number
  shadowBlurPx: number
  glowBlurPx: number
  color: string
  strokeColor: string
}

const PYTHON_SPECTRUM_BINS = 64
const PYTHON_SAMPLE_RATE = 44100
const PYTHON_NYQUIST = PYTHON_SAMPLE_RATE / 2
const PYTHON_MIN_FREQ = 20
const PYTHON_MAX_FREQ = 12000
const PYTHON_MIN_LOG = Math.log10(PYTHON_MIN_FREQ)
const PYTHON_MAX_LOG = Math.log10(PYTHON_MAX_FREQ)
const PYTHON_SMOOTH_KERNEL = [0.1, 0.2, 0.4, 0.2, 0.1] as const
const PYTHON_FREQ_BOOST = Float32Array.from({ length: PYTHON_SPECTRUM_BINS }, (_, index) => {
  const normalized = index / PYTHON_SPECTRUM_BINS
  return 1 + normalized * normalized * 2
})

function normalizeColor(value: unknown, fallback: string): string {
  const raw = typeof value === 'string' ? value.trim() : ''
  if (!raw) {
    return fallback
  }
  return raw.startsWith('#') ? raw : `#${raw}`
}

function toAlphaColor(color: string, alpha: number): string {
  const normalized = normalizeColor(color, '#ffffff')
  const safeAlpha = clamp(alpha, 0, 1)
  const hex = normalized.slice(1)
  const expanded =
    hex.length === 3
      ? hex
          .split('')
          .map((value) => value + value)
          .join('')
      : hex.padEnd(6, 'f').slice(0, 6)
  const red = Number.parseInt(expanded.slice(0, 2), 16)
  const green = Number.parseInt(expanded.slice(2, 4), 16)
  const blue = Number.parseInt(expanded.slice(4, 6), 16)
  return `rgba(${red}, ${green}, ${blue}, ${safeAlpha})`
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value))
}

function smoothstep01(value: number): number {
  const t = clamp(value, 0, 1)
  return t * t * (3 - 2 * t)
}

function averageValues(values: ArrayLike<number>, count = values.length): number {
  const safeCount = Math.max(0, Math.min(count, values.length))
  if (!safeCount) {
    return 0
  }

  let total = 0
  for (let index = 0; index < safeCount; index += 1) {
    total += values[index] ?? 0
  }
  return total / safeCount
}

export function precomputeSpectrumLogBinMapping(pointCount: number): SpectrumLogBinMapping {
  const fftSizeHalf = Math.max(1, pointCount)
  const idx1 = new Int32Array(PYTHON_SPECTRUM_BINS)
  const idx2 = new Int32Array(PYTHON_SPECTRUM_BINS)
  const frac = new Float32Array(PYTHON_SPECTRUM_BINS)

  for (let index = 0; index < PYTHON_SPECTRUM_BINS; index += 1) {
    const logFreq =
      PYTHON_MIN_LOG + (index / PYTHON_SPECTRUM_BINS) * (PYTHON_MAX_LOG - PYTHON_MIN_LOG)
    const frequency = 10 ** logFreq
    const linearIndex = (frequency / PYTHON_NYQUIST) * fftSizeHalf
    const lower = Math.floor(linearIndex)
    const upper = Math.min(Math.ceil(linearIndex), fftSizeHalf - 1)
    idx1[index] = lower
    idx2[index] = upper
    frac[index] = linearIndex - lower
  }

  return { idx1, idx2, frac }
}

function mapFrequencyDataToLogBins(
  frequencyData: Uint8Array,
  mapping: SpectrumLogBinMapping,
): Float32Array {
  const result = new Float32Array(PYTHON_SPECTRUM_BINS)
  const upperBound = Math.max(0, frequencyData.length - 1)

  for (let index = 0; index < PYTHON_SPECTRUM_BINS; index += 1) {
    const lowerIndex = Math.min(mapping.idx1[index], upperBound)
    const upperIndex = Math.min(mapping.idx2[index], upperBound)
    const lowerValue = (frequencyData[lowerIndex] ?? 0) / 255
    const upperValue = (frequencyData[upperIndex] ?? 0) / 255
    const interpolated = lowerValue * (1 - mapping.frac[index]) + upperValue * mapping.frac[index]
    result[index] = clamp(interpolated * PYTHON_FREQ_BOOST[index], 0.01, 1)
  }

  return result
}

function smoothSpectrumValues(values: Float32Array): Float32Array {
  const smoothed = new Float32Array(values.length)

  for (let index = 0; index < values.length; index += 1) {
    let total = 0
    for (let offset = -2; offset <= 2; offset += 1) {
      const sourceIndex = clamp(index + offset, 0, values.length - 1)
      total += values[sourceIndex] * PYTHON_SMOOTH_KERNEL[offset + 2]
    }
    smoothed[index] = total
  }

  if (values.length >= 4) {
    smoothed[0] = values[0]
    smoothed[1] = values[1]
    smoothed[values.length - 2] = values[values.length - 2]
    smoothed[values.length - 1] = values[values.length - 1]
  }

  return smoothed
}

function smoothSpectrumValuesCrisp(values: Float32Array): Float32Array {
  const smoothed = new Float32Array(values.length)
  const kernel = [0.15, 0.7, 0.15] as const

  for (let index = 0; index < values.length; index += 1) {
    const left = values[clamp(index - 1, 0, values.length - 1)]
    const mid = values[index]
    const right = values[clamp(index + 1, 0, values.length - 1)]
    smoothed[index] = left * kernel[0] + mid * kernel[1] + right * kernel[2]
  }

  if (values.length >= 2) {
    smoothed[0] = values[0]
    smoothed[values.length - 1] = values[values.length - 1]
  }

  return smoothed
}

function shapeSpectrumValues(
  values: Float32Array,
  kick: number,
  floorWeight: number,
  normalizationMax: number,
  options?: {
    minFloor?: number
    maxFloor?: number
    accentStrength?: number
    curveExp?: number
  },
): Float32Array {
  if (!values.length) {
    return values
  }

  const maxValue = Math.max(0.0001, normalizationMax)
  if (maxValue <= 0.0001) {
    return new Float32Array(values.length)
  }

  const averageValue = averageValues(values)
  const normalizedAverage = clamp(averageValue / maxValue, 0, 1)
  const minFloor = clamp(options?.minFloor ?? 0.03, 0, 0.35)
  const maxFloor = clamp(options?.maxFloor ?? 0.22, minFloor, 0.8)
  const accentStrength = clamp(options?.accentStrength ?? 0.55, 0, 2)
  const curveExp = clamp(options?.curveExp ?? 1.14, 0.6, 2.5)
  const floor = clamp(normalizedAverage * floorWeight, minFloor, maxFloor)
  const kickLift = clamp(kick, 0, 1) * 0.08
  const shaped = new Float32Array(values.length)

  for (let index = 0; index < values.length; index += 1) {
    const normalized = clamp(values[index] / maxValue, 0, 1)
    const left = index > 0 ? clamp(values[index - 1] / maxValue, 0, 1) : normalized
    const right = index + 1 < values.length ? clamp(values[index + 1] / maxValue, 0, 1) : normalized
    const localPeak = normalized - (left + right) * 0.5
    const separated = clamp((normalized - floor) / Math.max(0.0001, 1 - floor), 0, 1)
    const curved = Math.pow(separated, curveExp)
    const accent = clamp(localPeak * accentStrength, -0.08, 0.28)
    const bassWeight = 1 - Math.min(1, index / 12)
    shaped[index] = clamp(curved + accent + bassWeight * kickLift, 0, 1)
  }

  return shaped
}

function resolveSpectrumAnalysisProfile(styleFamily: string, dynamics: number): SpectrumAnalysisProfile {
  const normalizedStyle = normalizeSpectrumStyleKey(styleFamily)
  const dynamicsDial = clamp(dynamics, 0.5, 2.5)

  switch (normalizedStyle) {
    case 'straight-bars':
      return {
        smoothing: 'crisp',
        attackSec: 0.05,
        releaseSec: 0.32,
        floorSec: 2.2,
        floorMix: 0.86,
        localAccentBase: 0.22 + clamp(dynamicsDial - 1, 0, 1.5) * 0.04,
        localAccentLift: 0.12,
        meanLift: 0.12 / Math.max(0.4, dynamicsDial),
        tailTrim: 0.08 / Math.max(0.4, dynamicsDial),
        floorWeight: 0.18 / Math.max(0.5, dynamicsDial),
        minFloor: 0.008,
        maxFloor: 0.055,
        accentStrength: 1.25,
        curveExp: 1.06,
      }
    case 'orbital-bars':
      return {
        smoothing: 'crisp',
        attackSec: 0.04,
        releaseSec: 0.2,
        floorSec: 1.45,
        floorMix: 0.76,
        localAccentBase: 0.34,
        localAccentLift: 0.12,
        meanLift: 0.04,
        tailTrim: 0.016,
        floorWeight: 0.16,
        minFloor: 0.01,
        maxFloor: 0.08,
        accentStrength: 1.02,
        curveExp: 1,
      }
    case 'dot-matrix':
      return {
        smoothing: 'crisp',
        attackSec: 0.036,
        releaseSec: 0.18,
        floorSec: 1.3,
        floorMix: 0.8,
        localAccentBase: 0.4,
        localAccentLift: 0.14,
        meanLift: 0.03,
        tailTrim: 0.012,
        floorWeight: 0.14,
        minFloor: 0.009,
        maxFloor: 0.072,
        accentStrength: 1.08,
        curveExp: 1,
      }
    case 'flying-glow':
      return {
        smoothing: 'smooth',
        attackSec: 0.04,
        releaseSec: 0.22,
        floorSec: 1.5,
        floorMix: 0.74,
        localAccentBase: 0.28,
        localAccentLift: 0.1,
        meanLift: 0.045,
        tailTrim: 0.018,
        floorWeight: 0.18,
        minFloor: 0.01,
        maxFloor: 0.085,
        accentStrength: 0.9,
        curveExp: 0.98,
      }
    case 'wave-ribbon':
      return {
        smoothing: 'smooth',
        attackSec: 0.05,
        releaseSec: 0.25,
        floorSec: 1.6,
        floorMix: 0.72,
        localAccentBase: 0.26,
        localAccentLift: 0.08,
        meanLift: 0.03,
        tailTrim: 0.01,
        floorWeight: 0.22,
        minFloor: 0.014,
        maxFloor: 0.11,
        accentStrength: 0.86,
        curveExp: 0.96,
      }
    case 'liquid-mass':
      return {
        smoothing: 'smooth',
        attackSec: 0.055,
        releaseSec: 0.28,
        floorSec: 1.8,
        floorMix: 0.7,
        localAccentBase: 0.22,
        localAccentLift: 0.06,
        meanLift: 0.025,
        tailTrim: 0.008,
        floorWeight: 0.24,
        minFloor: 0.015,
        maxFloor: 0.12,
        accentStrength: 0.82,
        curveExp: 0.94,
      }
    case 'halo-stack':
      return {
        smoothing: 'smooth',
        attackSec: 0.045,
        releaseSec: 0.22,
        floorSec: 1.55,
        floorMix: 0.74,
        localAccentBase: 0.3,
        localAccentLift: 0.09,
        meanLift: 0.03,
        tailTrim: 0.012,
        floorWeight: 0.2,
        minFloor: 0.012,
        maxFloor: 0.095,
        accentStrength: 0.92,
        curveExp: 0.98,
      }
    default:
      return {
        smoothing: 'smooth',
        attackSec: 0.045,
        releaseSec: 0.24,
        floorSec: 1.6,
        floorMix: 0.74,
        localAccentBase: 0.3,
        localAccentLift: 0.09,
        meanLift: 0.035,
        tailTrim: 0.014,
        floorWeight: 0.22,
        minFloor: 0.012,
        maxFloor: 0.1,
        accentStrength: 0.92,
        curveExp: 1,
      }
  }
}

export function buildSeparatedSpectrumSourceValues(
  adjustedValues: Float32Array,
  deltaSec: number,
  envelope: SpectrumReactiveEnvelope,
  styleFamily: string,
  dynamics: number,
): {
  sourceValues: Float32Array
  framePeak: number
  averageValue: number
  profile: SpectrumAnalysisProfile
} {
  const normalizedStyle = normalizeSpectrumStyleKey(styleFamily)
  const profile = resolveSpectrumAnalysisProfile(normalizedStyle, dynamics)
  if (envelope.styleKey !== normalizedStyle) {
    envelope.styleKey = normalizedStyle
    envelope.bins = null
    envelope.floorBins = null
  }
  if (!envelope.bins || envelope.bins.length !== PYTHON_SPECTRUM_BINS) {
    envelope.bins = new Float32Array(PYTHON_SPECTRUM_BINS)
  }
  if (!envelope.floorBins || envelope.floorBins.length !== PYTHON_SPECTRUM_BINS) {
    envelope.floorBins = new Float32Array(PYTHON_SPECTRUM_BINS)
  }

  const sourceValues = new Float32Array(PYTHON_SPECTRUM_BINS)
  const attackA = 1 - Math.exp(-deltaSec / profile.attackSec)
  const releaseA = 1 - Math.exp(-deltaSec / profile.releaseSec)
  const floorA = 1 - Math.exp(-deltaSec / profile.floorSec)
  let framePeak = 0
  let averageValue = 0

  for (let index = 0; index < PYTHON_SPECTRUM_BINS; index += 1) {
    const prev = envelope.bins[index] ?? 0
    const next = adjustedValues[index]
    const mix = next > prev ? attackA : releaseA
    const blended = prev * (1 - mix) + next * mix
    envelope.bins[index] = blended

    const floorPrev = envelope.floorBins[index] ?? 0
    const floorNext = floorPrev * (1 - floorA) + blended * floorA
    envelope.floorBins[index] = floorNext

    const separated = Math.max(0, blended - floorNext * profile.floorMix)
    sourceValues[index] = separated
    framePeak = Math.max(framePeak, separated)
    averageValue += separated
  }

  averageValue /= PYTHON_SPECTRUM_BINS
  const baseValues = sourceValues.slice()
  const loudness = clamp(averageValue / Math.max(0.0001, framePeak), 0, 1)
  const accentBlend = profile.localAccentBase + (1 - loudness) * profile.localAccentLift
  const meanLift = averageValue * profile.meanLift

  framePeak = 0
  let enhancedAverage = 0
  for (let index = 0; index < PYTHON_SPECTRUM_BINS; index += 1) {
    const value = baseValues[index]
    const left = baseValues[Math.max(0, index - 1)]
    const right = baseValues[Math.min(PYTHON_SPECTRUM_BINS - 1, index + 1)]
    const local = Math.max(0, value - (left + right) * 0.5)
    const enhanced = Math.max(0, value + local * accentBlend - meanLift - averageValue * profile.tailTrim)
    sourceValues[index] = enhanced
    framePeak = Math.max(framePeak, enhanced)
    enhancedAverage += enhanced
  }

  return {
    sourceValues,
    framePeak,
    averageValue: enhancedAverage / PYTHON_SPECTRUM_BINS,
    profile,
  }
}

function resolveAnchorAlignment(anchor: string): {
  horizontal: 'left' | 'center' | 'right'
  vertical: 'top' | 'middle' | 'bottom'
} {
  const normalized = String(anchor || 'center').trim().toLowerCase()
  return {
    horizontal: normalized.endsWith('left')
      ? 'left'
      : normalized.endsWith('right')
        ? 'right'
        : 'center',
    vertical: normalized.startsWith('top')
      ? 'top'
      : normalized.startsWith('bottom')
        ? 'bottom'
        : 'middle',
  }
}

function resolveAnchoredRect(
  anchor: string,
  offsetX: number,
  offsetY: number,
  width: number,
  height: number,
  boundsWidth: number,
  boundsHeight: number,
): { x: number; y: number } {
  const point = resolveAnchorPoint(anchor, boundsWidth, boundsHeight)
  const alignment = resolveAnchorAlignment(anchor)

  const x =
    alignment.horizontal === 'center'
      ? point.x - width * 0.5 + offsetX
      : alignment.horizontal === 'right'
        ? point.x - width + offsetX
        : point.x + offsetX
  const y =
    alignment.vertical === 'middle'
      ? point.y - height * 0.5 + offsetY
      : alignment.vertical === 'bottom'
        ? point.y - height + offsetY
        : point.y + offsetY

  return { x, y }
}

function traceRoundedRect(
  context: CanvasRenderingContext2D,
  x: number,
  y: number,
  width: number,
  height: number,
  radius: number,
): void {
  const safeRadius = clamp(radius, 0, Math.min(width, height) * 0.5)
  context.beginPath()
  context.moveTo(x + safeRadius, y)
  context.lineTo(x + width - safeRadius, y)
  context.quadraticCurveTo(x + width, y, x + width, y + safeRadius)
  context.lineTo(x + width, y + height - safeRadius)
  context.quadraticCurveTo(x + width, y + height, x + width - safeRadius, y + height)
  context.lineTo(x + safeRadius, y + height)
  context.quadraticCurveTo(x, y + height, x, y + height - safeRadius)
  context.lineTo(x, y + safeRadius)
  context.quadraticCurveTo(x, y, x + safeRadius, y)
  context.closePath()
}

function drawPlaceholderBackground(
  context: CanvasRenderingContext2D,
  width: number,
  height: number,
): void {
  const glow = context.createRadialGradient(width * 0.5, 0, 0, width * 0.5, 0, Math.max(width, height) * 0.7)
  glow.addColorStop(0, 'rgba(217,70,239,0.18)')
  glow.addColorStop(1, 'rgba(217,70,239,0)')
  context.fillStyle = 'rgba(18,27,54,0.92)'
  context.fillRect(0, 0, width, height)
  context.fillStyle = glow
  context.fillRect(0, 0, width, height)
  const depth = context.createLinearGradient(0, 0, 0, height)
  depth.addColorStop(0, 'rgba(18,27,54,0.92)')
  depth.addColorStop(1, 'rgba(3,7,18,1)')
  context.fillStyle = depth
  context.fillRect(0, 0, width, height)
}

function buildDomLogoBoxShadow(presentation: LogoPresentationState): string {
  const outlineColor = toAlphaColor('#f8fbff', presentation.outlineAlpha)
  const glowColor = toAlphaColor('#8b5cf6', presentation.glowAlpha)
  const depthColor = toAlphaColor('#020617', presentation.depthAlpha)
  return [
    `0 0 0 1px ${outlineColor}`,
    `0 ${presentation.shadowOffsetYPx.toFixed(1)}px ${(presentation.shadowBlurPx * 0.82).toFixed(1)}px ${depthColor}`,
    `0 0 ${presentation.shadowBlurPx.toFixed(1)}px ${glowColor}`,
  ].join(', ')
}

function applyDomBackgroundPresentation(
  node: HTMLImageElement,
  presentation: BackgroundPresentationState,
): void {
  node.style.objectFit = presentation.objectFit
  node.style.objectPosition = 'center center'
  node.style.filter = `brightness(${presentation.brightness})`
  node.style.transform = `translate3d(${presentation.translateX.toFixed(2)}px, ${presentation.translateY.toFixed(2)}px, 0) scale(${presentation.scale.toFixed(4)})`
  node.style.transformOrigin = 'center center'
  node.style.willChange = 'transform, filter'
}

function applyDomLogoPresentation(
  node: HTMLDivElement,
  presentation: LogoPresentationState,
): void {
  node.style.left = `${presentation.x}px`
  node.style.top = `${presentation.y}px`
  node.style.width = `${presentation.size}px`
  node.style.height = `${presentation.size}px`
  node.style.opacity = `${presentation.opacity}`
  node.style.borderRadius = `${presentation.borderRadiusPx}px`
  node.style.transform = presentation.rotationDeg ? `rotate(${presentation.rotationDeg}deg)` : 'none'
  node.style.transformOrigin = 'center center'
  node.style.boxShadow = buildDomLogoBoxShadow(presentation)
  node.style.willChange = 'transform, box-shadow, opacity'
}

function drawBackgroundLayer(
  context: CanvasRenderingContext2D,
  backgroundImage: HTMLImageElement | null,
  width: number,
  height: number,
  presentation: BackgroundPresentationState,
): void {
  if (!backgroundImage) {
    drawPlaceholderBackground(context, width, height)
  } else {
    context.save()
    context.filter = `brightness(${presentation.brightness})`
    context.drawImage(
      backgroundImage,
      presentation.drawX,
      presentation.drawY,
      presentation.drawWidth,
      presentation.drawHeight,
    )
    context.restore()
  }

  context.save()
  const wash = context.createLinearGradient(0, 0, 0, height)
  wash.addColorStop(0, 'rgba(2,6,23,0.06)')
  wash.addColorStop(1, 'rgba(2,6,23,0.36)')
  context.fillStyle = wash
  context.fillRect(0, 0, width, height)
  context.restore()
}

function wrapTextLine(
  context: CanvasRenderingContext2D,
  text: string,
  maxWidth: number,
): string[] {
  if (!text.trim()) {
    return ['']
  }

  const tokens = text.split(/\s+/).filter(Boolean)
  const lines: string[] = []
  let current = ''

  const pushLongToken = (token: string) => {
    let segment = ''
    for (const char of token) {
      const nextSegment = segment + char
      if (segment && context.measureText(nextSegment).width > maxWidth) {
        lines.push(segment)
        segment = char
      } else {
        segment = nextSegment
      }
    }
    if (segment) {
      current = segment
    }
  }

  tokens.forEach((token) => {
    const candidate = current ? `${current} ${token}` : token
    if (context.measureText(candidate).width <= maxWidth) {
      current = candidate
      return
    }

    if (current) {
      lines.push(current)
      current = ''
    }

    if (context.measureText(token).width > maxWidth) {
      pushLongToken(token)
      return
    }

    current = token
  })

  if (current) {
    lines.push(current)
  }

  return lines.length ? lines : ['']
}

function wrapTextBlock(
  context: CanvasRenderingContext2D,
  text: string,
  maxWidth: number,
): string[] {
  return text.split(/\r?\n/).flatMap((line) => wrapTextLine(context, line, maxWidth))
}

function drawLogoLayer(
  context: CanvasRenderingContext2D,
  draft: PreviewLogoDrawDraft,
  logoImage: HTMLImageElement | null,
  presentation: LogoPresentationState,
): void {
  if (!draft.logoEnabled || !logoImage) {
    return
  }

  const sourceSize = Math.min(
    logoImage.naturalWidth || logoImage.width || presentation.size,
    logoImage.naturalHeight || logoImage.height || presentation.size,
  )
  const sourceX = Math.max(0, ((logoImage.naturalWidth || sourceSize) - sourceSize) * 0.5)
  const sourceY = Math.max(0, ((logoImage.naturalHeight || sourceSize) - sourceSize) * 0.5)

  context.save()
  context.translate(presentation.centerX, presentation.centerY)
  if (presentation.rotationRad) {
    context.rotate(presentation.rotationRad)
  }
  context.globalAlpha = presentation.opacity

  context.save()
  context.shadowColor = toAlphaColor('#8b5cf6', presentation.glowAlpha)
  context.shadowBlur = presentation.shadowBlurPx
  context.shadowOffsetY = presentation.shadowOffsetYPx
  context.strokeStyle = toAlphaColor('#f8fbff', presentation.outlineAlpha)
  context.lineWidth = Math.max(1, presentation.size * 0.018)
  if (draft.logoShape === 'circle') {
    context.beginPath()
    context.arc(0, 0, presentation.size * 0.5, 0, Math.PI * 2)
    context.closePath()
  } else {
    traceRoundedRect(
      context,
      -presentation.size * 0.5,
      -presentation.size * 0.5,
      presentation.size,
      presentation.size,
      presentation.borderRadiusPx,
    )
  }
  context.stroke()
  context.restore()

  if (draft.logoShape === 'circle') {
    context.beginPath()
    context.arc(0, 0, presentation.size * 0.5, 0, Math.PI * 2)
    context.closePath()
    context.clip()
  } else {
    traceRoundedRect(
      context,
      -presentation.size * 0.5,
      -presentation.size * 0.5,
      presentation.size,
      presentation.size,
      presentation.borderRadiusPx,
    )
    context.clip()
  }

  context.drawImage(
    logoImage,
    sourceX,
    sourceY,
    sourceSize,
    sourceSize,
    -presentation.size * 0.5,
    -presentation.size * 0.5,
    presentation.size,
    presentation.size,
  )
  context.restore()
}

function drawTextOverlays(
  context: CanvasRenderingContext2D,
  overlays: ReadonlyArray<ResolvedTextOverlayPreview>,
  width: number,
  height: number,
): void {
  overlays.forEach((overlay) => {
    const maxWidth = Math.max(80, width * 0.88)
    context.save()
    context.font = `800 ${Math.max(10, overlay.fontSizePx)}px Inter, ui-sans-serif, system-ui, sans-serif`
    const lines = wrapTextBlock(context, overlay.text, maxWidth)
    const lineHeight = overlay.fontSizePx * 1.08
    const measuredWidth = lines.reduce(
      (maxLineWidth, line) => Math.max(maxLineWidth, context.measureText(line).width),
      0,
    )
    const blockWidth = Math.min(maxWidth, Math.max(1, measuredWidth))
    const blockHeight = Math.max(lineHeight, lines.length * lineHeight)
    const rect = resolveAnchoredRect(
      overlay.anchor,
      overlay.offsetX,
      overlay.offsetY,
      blockWidth,
      blockHeight,
      width,
      height,
    )
    const pivotX =
      overlay.textAlign === 'center'
        ? rect.x + blockWidth * 0.5
        : overlay.textAlign === 'right'
          ? rect.x + blockWidth
          : rect.x
    const pivotY = rect.y + blockHeight * 0.5

    context.translate(pivotX, pivotY)
    if (Math.abs(overlay.textScale - 1) > 0.001) {
      context.scale(overlay.textScale, overlay.textScale)
    }
    context.translate(-pivotX, -pivotY)
    context.globalAlpha = clamp(overlay.opacity, 0, 1)
    context.textAlign = overlay.textAlign
    context.textBaseline = 'alphabetic'
    context.lineJoin = 'round'
    context.lineWidth = Math.max(0, overlay.strokeWidthPx)

    const drawX =
      overlay.textAlign === 'center'
        ? rect.x + blockWidth * 0.5
        : overlay.textAlign === 'right'
          ? rect.x + blockWidth
          : rect.x
    let currentY = rect.y + overlay.fontSizePx

    lines.forEach((line) => {
      if (overlay.glowBlurPx > 0) {
        context.shadowColor = toAlphaColor(overlay.color, 0.9)
        context.shadowBlur = overlay.glowBlurPx
      } else if (overlay.shadowBlurPx > 0) {
        context.shadowColor = 'rgba(0, 0, 0, 0.8)'
        context.shadowBlur = overlay.shadowBlurPx
      } else {
        context.shadowColor = 'rgba(0,0,0,0)'
        context.shadowBlur = 0
      }

      if (overlay.strokeWidthPx > 0) {
        context.strokeStyle = overlay.strokeColor
        context.strokeText(line, drawX, currentY)
      }

      context.fillStyle = overlay.color
      context.fillText(line, drawX, currentY)
      currentY += lineHeight
    })

    context.restore()
  })
}

function smoothStep(value: number): number {
  const unit = clamp(value, 0, 1)
  return unit * unit * (3 - 2 * unit)
}

function resolveAnimatedTextOverlay(
  overlay: TemplateTextOverlayDraft,
  index: number,
  currentTimeSec: number,
  scale: number,
  isSelected: boolean,
): ResolvedTextOverlayPreview | null {
  if (!overlay.enabled) {
    return null
  }

  const rawText = overlay.text.trim() || `Text ${index + 1}`
  const durationSec = Math.max(0, overlay.durationSec)
  if (durationSec <= 0) {
    return null
  }

  const startSec = Math.max(0, overlay.startSec)
  const relativeTimeSec = currentTimeSec - startSec
  if (relativeTimeSec < 0 || relativeTimeSec > durationSec) {
    return null
  }

  const progress = clamp(relativeTimeSec / durationSec, 0, 1)
  const ease = smoothStep(progress)
  const animation = String(overlay.animation || 'fade').trim().toLowerCase()
  const fadeIn = 0.18
  const fadeOut = 0.18
  const fadeInAlpha = Math.min(1, progress / Math.max(0.001, fadeIn))
  const fadeOutAlpha = Math.min(1, (1 - progress) / Math.max(0.001, fadeOut))

  let opacity = 1
  let dx = 0
  let dy = 0
  let textScale = 1
  let reveal = 1
  let glowBlurPx = 0

  if (['fade', 'slide_up', 'slide_down', 'slide_left', 'slide_right', 'pop', 'typewriter', 'glow', 'shake'].includes(animation)) {
    opacity = clamp(fadeInAlpha * fadeOutAlpha, 0, 1)
  }

  if (animation === 'slide_up') {
    dy -= (1 - ease) * 60 * scale
  } else if (animation === 'slide_down') {
    dy += (1 - ease) * 60 * scale
  } else if (animation === 'slide_left') {
    dx -= (1 - ease) * 70 * scale
  } else if (animation === 'slide_right') {
    dx += (1 - ease) * 70 * scale
  } else if (animation === 'pop') {
    textScale = clamp(0.85 + ease * 0.2, 0.3, 2.5)
  } else if (animation === 'typewriter') {
    reveal = clamp(progress * 1.2, 0, 1)
  } else if (animation === 'glow') {
    opacity *= 0.78 + 0.22 * Math.sin(progress * Math.PI * 4)
    glowBlurPx = Math.max(8, overlay.fontSize * scale * 0.18)
  } else if (animation === 'shake') {
    const shakeBlend = progress * (1 - progress)
    dx += Math.sin((startSec + currentTimeSec) * 38 + index * 7) * 10 * scale * shakeBlend
    dy += Math.cos((startSec + currentTimeSec) * 41 + index * 11) * 10 * scale * shakeBlend
  }

  const revealedCharacters = Math.max(1, Math.ceil(rawText.length * reveal))
  const displayText = animation === 'typewriter' ? rawText.slice(0, revealedCharacters) : rawText
  return {
    key: `renderer-text-${index}`,
    index,
    text: displayText,
    anchor: overlay.anchor,
    offsetX: overlay.x * scale + dx,
    offsetY: overlay.y * scale + dy,
    textScale,
    opacity: clamp(opacity, 0, 1),
    textAlign: overlay.anchor.endsWith('left')
      ? 'left'
      : overlay.anchor.endsWith('right')
        ? 'right'
        : 'center',
    fontSizePx: Math.max(10, overlay.fontSize * scale),
    strokeWidthPx: Math.max(0, overlay.strokeWidth * scale),
    shadowBlurPx: overlay.shadow > 0 ? Math.max(4, 18 * overlay.shadow * scale) : 0,
    glowBlurPx: glowBlurPx + (isSelected ? 4 * scale : 0),
    color: overlay.color,
    strokeColor: overlay.strokeColor,
  }
}

function resolveAnchorPoint(anchor: string, width: number, height: number): { x: number; y: number } {
  switch (anchor) {
    case 'top-left':
      return { x: 0, y: 0 }
    case 'top-right':
      return { x: width, y: 0 }
    case 'bottom-left':
      return { x: 0, y: height }
    case 'bottom-right':
      return { x: width, y: height }
    case 'top-center':
      return { x: width / 2, y: 0 }
    case 'bottom-center':
      return { x: width / 2, y: height }
    case 'center-left':
      return { x: 0, y: height / 2 }
    case 'center-right':
      return { x: width, y: height / 2 }
    case 'center':
    default:
      return { x: width / 2, y: height / 2 }
  }
}

export function buildAnalyserSpectrumValues(
  frequencyData: Uint8Array | null,
  sensitivity: number,
  dynamics: number,
  kickDrop: number,
  deltaSec: number,
  mapping: SpectrumLogBinMapping | null,
  envelope: SpectrumReactiveEnvelope,
  styleFamily: string,
): AnalysedSpectrumFrame | null {
  if (!frequencyData?.length || !mapping) {
    return null
  }

  const fftLog = mapFrequencyDataToLogBins(frequencyData, mapping)
  const safeSensitivity = clamp(sensitivity, 0.1, 8)
  const adjustedValues = new Float32Array(PYTHON_SPECTRUM_BINS)

  for (let index = 0; index < PYTHON_SPECTRUM_BINS; index += 1) {
    adjustedValues[index] = clamp(fftLog[index] * safeSensitivity, 0, 2.5)
  }

  const normalizedStyle = normalizeSpectrumStyleKey(styleFamily)
  const { sourceValues, framePeak, averageValue: separatedAverage, profile } = buildSeparatedSpectrumSourceValues(
    adjustedValues,
    deltaSec,
    envelope,
    normalizedStyle,
    dynamics,
  )
  let straightAvg = separatedAverage

  const levelA = 1 - Math.exp(-deltaSec / 0.5)
  envelope.level = envelope.level * (1 - levelA) + framePeak * levelA

  const bass = averageValues(adjustedValues, 6)
  const kickFastA = 1 - Math.exp(-deltaSec / 0.06)
  const kickSlowA = 1 - Math.exp(-deltaSec / 0.35)
  const kickDecay = Math.exp(-deltaSec / 0.18)
  envelope.bassFast = envelope.bassFast * (1 - kickFastA) + bass * kickFastA
  envelope.bassSlow = envelope.bassSlow * (1 - kickSlowA) + bass * kickSlowA
  envelope.kick = Math.max(0, Math.max(envelope.bassFast - envelope.bassSlow, envelope.kick * kickDecay))
  const bassCore = averageValues(adjustedValues, 4)
  const lowMid = averageValues(adjustedValues.subarray(4, 12))
  const kickContrast = Math.max(0, envelope.bassFast - envelope.bassSlow)
  const dropTrigger = clamp(bassCore * 0.78 + kickContrast * 0.72 - lowMid * 0.82, 0, 1.2)
  const dropAttackA = 1 - Math.exp(-deltaSec / 0.022)
  const dropReleaseA = 1 - Math.exp(-deltaSec / 0.085)
  const dropMix = dropTrigger > envelope.drop ? dropAttackA : dropReleaseA
  envelope.drop = envelope.drop * (1 - dropMix) + dropTrigger * dropMix

  const normalizationMax = Math.max(0.0001, Math.max(framePeak, envelope.level))
  const smoothedValues = profile.smoothing === 'crisp' ? smoothSpectrumValuesCrisp(sourceValues) : smoothSpectrumValues(sourceValues)
  const shapedValues = shapeSpectrumValues(
    smoothedValues,
    envelope.kick,
    profile.floorWeight,
    normalizationMax,
    {
      minFloor: profile.minFloor,
      maxFloor: profile.maxFloor,
      accentStrength: profile.accentStrength,
      curveExp: profile.curveExp,
    },
  )
  const kickDropDial = clamp(kickDrop, 0, 2)
  if (normalizedStyle === 'straight-bars') {
    const dynamicsDial = clamp(dynamics, 0.5, 2.5)
    const avg = averageValues(shapedValues)
    const contrast = 1.45 + clamp(straightAvg * 0.9, 0, 0.45)
    const gate = clamp(avg * (0.34 - (dynamicsDial - 1) * 0.06) - envelope.kick * 0.03, 0.008, 0.11)
    const invRange = 1 / Math.max(0.0001, 1 - gate)
    for (let index = 0; index < shapedValues.length; index += 1) {
      const gated = (shapedValues[index] - gate) * invRange
      shapedValues[index] = Math.pow(smoothstep01(gated), contrast * dynamicsDial)
    }
    if (kickDropDial > 0.001) {
      const transientLift = smoothstep01(envelope.drop * 0.94) * kickDropDial
      for (let index = 0; index < shapedValues.length; index += 1) {
        const normalizedIndex = index / Math.max(1, shapedValues.length - 1)
        const wingProfile = Math.pow(Math.sin(normalizedIndex * Math.PI), 1.12)
        const edgeProfile = Math.pow(Math.abs(normalizedIndex - 0.5) * 2, 1.35)
        const bassWeight = 1 - Math.min(1, index / 10)
        const boost =
          transientLift *
          (0.08 + wingProfile * 0.24 + (1 - bassWeight) * 0.14 + edgeProfile * 0.06)
        shapedValues[index] = clamp(shapedValues[index] * (1 + boost), 0, 1)
      }
    }
  }
  if (normalizedStyle === 'flying-glow') {
    // Flying Glow keeps a subtle circular waveform bed for general music,
    // then adds a larger shoulder-wing flare on kick/drop transients.
    const kickStart = smoothstep01(clamp((envelope.kick - 0.01) * 6.4, 0, 1.4))
    const wingBeat = Math.pow(smoothstep01(clamp((envelope.drop - 0.015) * (3 + kickDropDial * 0.6), 0, 1.3)), 0.82)
    const wingPulse = clamp(kickStart * 0.9 + wingBeat * (0.75 + kickDropDial * 0.28), 0.004, 1)
    const waveformBedEnergy = smoothstep01(clamp(envelope.level * 0.9, 0, 1))

    for (let index = 0; index < shapedValues.length; index += 1) {
      const normalizedIndex = index / Math.max(1, shapedValues.length - 1)
      const leftShoulder = Math.exp(-(((normalizedIndex - 0.18) / 0.16) ** 2))
      const rightShoulder = Math.exp(-(((normalizedIndex - 0.82) / 0.16) ** 2))
      const shoulderBias = Math.max(leftShoulder, rightShoulder)
      const centerDip = Math.exp(-(((normalizedIndex - 0.5) / 0.18) ** 2))
      const wingBias = clamp(0.16 + shoulderBias * 0.72 - centerDip * 0.12, 0.05, 1.08)
      const restFloor = 0.003
      const circularWave = Math.pow(shapedValues[index], 0.94) * (0.075 + waveformBedEnergy * 0.05)
      const kickSpike =
        wingBias *
        (0.08 + Math.pow(shapedValues[index], 0.78) * 0.64 + envelope.drop * 0.12) *
        Math.pow(wingPulse, 0.84)
      shapedValues[index] = clamp(restFloor + circularWave + kickSpike, 0, 1)
    }
  }
  const averageEnergy = averageValues(shapedValues)
  const reactiveEnergy =
    normalizedStyle === 'flying-glow'
      ? clamp(
          averageEnergy * 0.55 +
            smoothstep01(clamp(envelope.level * 0.75, 0, 1)) * 0.08 +
            envelope.kick * 0.62 +
            envelope.drop * (0.48 + kickDropDial * 0.28),
          0,
          1,
        )
      : clamp(averageEnergy + envelope.kick * 0.35 + envelope.drop * kickDropDial * 0.18, 0, 1)

  return {
    smoothedValues: shapedValues,
    reactiveEnergy,
  }
}

export function RendererVideoPreview(
  props: RendererVideoPreviewProps,
): React.JSX.Element {
  const templateDraft = useMemo(
    () => props.templateDraft ?? buildVideoTemplateDraft(props.template, { logoPath: '' }),
    [props.template, props.templateDraft],
  )
  return (
    <PreviewProvider
      applyDomBackgroundPresentation={applyDomBackgroundPresentation}
      applyDomLogoPresentation={applyDomLogoPresentation}
      averageValues={averageValues}
      backgroundPath={props.backgroundPath}
      buildDomBackgroundStyle={({ backgroundImage, bounds, currentPlaybackTimeSec, templateDraft }) => {
        const presentation = resolveBackgroundPresentationState(
          templateDraft,
          bounds.width,
          bounds.height,
          Math.max(1, backgroundImage?.naturalWidth || backgroundImage?.width || bounds.width),
          Math.max(1, backgroundImage?.naturalHeight || backgroundImage?.height || bounds.height),
          0,
          currentPlaybackTimeSec,
        )
        return {
          objectFit: presentation.objectFit,
          objectPosition: 'center center',
          filter: `brightness(${presentation.brightness})`,
          transform: `translate3d(${presentation.translateX.toFixed(2)}px, ${presentation.translateY.toFixed(2)}px, 0) scale(${presentation.scale.toFixed(4)})`,
          transformOrigin: 'center center',
          willChange: 'transform, filter',
        }
      }}
      buildDomLogoStyle={({ bounds, currentPlaybackTimeSec, scale, templateDraft }) => {
        const presentation = resolveLogoPresentationState(
          templateDraft,
          bounds.width,
          bounds.height,
          scale,
          0,
          currentPlaybackTimeSec,
        )
        return {
          left: `${presentation.x}px`,
          top: `${presentation.y}px`,
          width: `${presentation.size}px`,
          height: `${presentation.size}px`,
          opacity: presentation.opacity,
          borderRadius: `${presentation.borderRadiusPx}px`,
          boxShadow: buildDomLogoBoxShadow(presentation),
          transform: presentation.rotationDeg ? `rotate(${presentation.rotationDeg}deg)` : 'none',
          transformOrigin: 'center center',
          willChange: 'transform, box-shadow, opacity',
        }
      }}
      buildLayerSpectrumValues={buildLayerSpectrumValues}
      buildSyntheticSpectrumValues={buildSyntheticSpectrumValues}
      drawBackgroundLayer={drawBackgroundLayer}
      drawLogoLayer={drawLogoLayer}
      drawTextOverlays={drawTextOverlays}
      logoPath={props.logoPath}
      onPlaybackStateChange={props.onPlaybackStateChange}
      playbackCommand={props.playbackCommand}
      previewVolume={props.previewVolume}
      runtimeMode={props.runtimeMode}
      resolveAnchorPoint={resolveAnchorPoint}
      resolveSpectrumBarCount={({ bounds, scale, spectrumAttachment, spectrumLayers, templateDraft }) => {
        return resolveSpectrumBarCount({
          bounds,
          scale,
          spectrumAttachment,
          spectrumLayers,
          templateDraft,
          resolveAnchorPoint,
        })
      }}
      resolveTextOverlayState={({ currentPlaybackTimeSec, scale, selectedTextOverlayIndex, templateDraft }) => ({
        activeTextOverlays: (templateDraft.textOverlays ?? [])
          .map((overlay, index) =>
            resolveAnimatedTextOverlay(
              overlay,
              index,
              currentPlaybackTimeSec,
              scale,
              selectedTextOverlayIndex === index,
            ),
          )
          .filter((overlay): overlay is ResolvedTextOverlayPreview => Boolean(overlay)),
        enabledTextOverlayCount: (templateDraft.textOverlays ?? []).filter((overlay) => overlay.enabled).length,
      })}
      selectedMp3Path={props.selectedMp3Path}
      selectedTextOverlayIndex={props.selectedTextOverlayIndex}
      smoothPreviewReactiveValue={smoothPreviewReactiveValue}
      template={props.template}
      templateDraft={templateDraft}
      updateFlyingGlowWingEnvelope={updateFlyingGlowWingEnvelope}
      workspace={props.workspace}
    >
      {(previewState) => (
        <RendererVideoPreviewSurfaceBridge
          previewState={previewState}
          enableSpectrumPositionEditing={props.enableSpectrumPositionEditing}
          onLifecycleStateChange={props.onLifecycleStateChange}
          onManualRenderFrameReady={props.onManualRenderFrameReady}
          onReadbackFrameCaptureReady={props.onReadbackFrameCaptureReady}
          onSpectrumPositionChange={props.onSpectrumPositionChange}
        />
      )}
    </PreviewProvider>
  )
}
