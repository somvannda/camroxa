import type { PreviewSpectrumBarCountDraft } from '@/features/video/core/contracts/previewDraftContracts'
import type { SpectrumAttachment } from '@/features/video/core/scene/attachmentService'
import type { AudioSpectrumFrame } from '@/features/video/preview/audioSpectrumAnalysis'
import type { SpectrumLayerPreview } from '@/features/video/domains/spectrum/spectrumLayerModel'
import { normalizeSpectrumStyleKey } from '@/features/video/domains/spectrum/spectrumLayerModel'

type SpectrumPreviewBounds = {
  width: number
  height: number
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value))
}

function mirrorSpectrumValues(values: Float32Array): Float32Array {
  const mirrored = new Float32Array(values.length)
  const half = Math.floor(values.length / 2)
  const left = values.slice(0, half)
  mirrored.set(left.slice().reverse(), 0)
  mirrored.set(left, half)
  return mirrored
}

function resampleSpectrumValues(values: Float32Array, count: number): number[] {
  if (count <= 0 || values.length <= 0) {
    return []
  }
  if (count === values.length) {
    return Array.from(values, (value) => clamp(value, 0.005, 1))
  }

  return Array.from({ length: count }, (_, index) => {
    const position = (index / Math.max(1, count - 1)) * (values.length - 1)
    const lower = Math.floor(position)
    const upper = Math.min(values.length - 1, Math.ceil(position))
    const fraction = position - lower
    const value = values[lower] * (1 - fraction) + values[upper] * fraction
    return clamp(value, 0.005, 1)
  })
}

function getSpectrumBarCount(style: string): number {
  const normalized = normalizeSpectrumStyleKey(style)
  switch (normalized) {
    case 'classic-vertical':
    case 'straight-bars':
      return 140
    case 'thin-lines':
      return 84
    case 'symmetrical-bars':
      return 64
    case 'pixel-bars':
      return 44
    case 'floating-blocks':
      return 36
    case 'neon-pulse':
      return 72
    case 'flying-glow':
      return 180
    case 'halo-stack':
      return 160
    case 'orbital-bars':
      return 88
    case 'dot-matrix':
      return 40
    case 'soft-waveform':
    case 'continuous-waveform':
    case 'wave-ribbon':
      return 88
    case 'mountain':
      return 72
    case 'liquid':
    case 'liquid-mass':
      return 76
    default:
      return 68
  }
}

function getStraightBarsBarCount({
  templateDraft,
  bounds,
  scale,
  spectrumAttachment,
  spectrumLayers,
  resolveAnchorPoint,
}: {
  templateDraft: PreviewSpectrumBarCountDraft
  bounds: SpectrumPreviewBounds
  scale: number
  spectrumAttachment: SpectrumAttachment | null
  spectrumLayers: SpectrumLayerPreview[]
  resolveAnchorPoint: (anchor: string, width: number, height: number) => { x: number; y: number }
}): number {
  const anchorPoint = resolveAnchorPoint(templateDraft.anchor, bounds.width, bounds.height)
  const centerX = anchorPoint.x + templateDraft.positionX * scale + (spectrumAttachment?.centerOffsetX ?? 0)
  const centerY = anchorPoint.y + templateDraft.positionY * scale + (spectrumAttachment?.centerOffsetY ?? 0)
  const gravity = String(spectrumLayers[0]?.gravity ?? 'bottom').trim().toLowerCase()
  const totalLength =
    gravity === 'left' || gravity === 'right'
      ? Math.max(48, centerY * 2 * 0.8)
      : Math.max(48, centerX * 2 * 0.8)
  const referenceCount = 140
  const referenceWidth = 4
  const targetWidth = 2
  const referenceStep = totalLength / referenceCount
  const gap = Math.max(0.25, referenceStep - referenceWidth)
  const targetStep = Math.max(0.5, gap + targetWidth)
  const derived = Math.round(totalLength / targetStep)
  return Math.round(clamp(derived, referenceCount, 240))
}

export function buildLayerSpectrumValues(
  count: number,
  frame: AudioSpectrumFrame | null,
  mirrored: boolean,
): number[] | null {
  if (!frame) {
    return null
  }
  const renderValues = mirrored ? mirrorSpectrumValues(frame.renderValues) : frame.renderValues
  return resampleSpectrumValues(renderValues, count)
}

export function buildSyntheticSpectrumValues(
  count: number,
  timeSec: number,
  sensitivity: number,
  smoothing: number,
  layerIndex: number,
): number[] {
  const safeSensitivity = clamp(sensitivity, 0.25, 4)
  const smoothFactor = clamp(smoothing, 0, 0.97)

  return Array.from({ length: count }, (_, index) => {
    const phase = timeSec * (1.55 + layerIndex * 0.2)
    const sweep = (Math.sin(phase * 2.3 + index * 0.31) + 1) / 2
    const pulse = (Math.sin(phase * 4.8 + index * 0.63 + layerIndex) + 1) / 2
    const shimmer = (Math.sin(phase * 7.6 + index * 0.17) + 1) / 2
    const composite = sweep * 0.55 + pulse * 0.3 + shimmer * 0.15
    const boosted = Math.pow(composite, Math.max(0.45, 1 - smoothFactor * 0.45))
    return clamp(boosted * safeSensitivity * 0.78, 0.08, 1)
  })
}

export function smoothPreviewReactiveValue(
  current: number,
  target: number,
  deltaSec: number,
  smoothing: number,
): number {
  const safeCurrent = Number.isFinite(current) ? current : 0
  const safeTarget = clamp(Number.isFinite(target) ? target : 0, 0, 1)
  const safeDelta = clamp(Number.isFinite(deltaSec) ? deltaSec : 1 / 60, 1 / 240, 0.25)
  const smoothDial = clamp(smoothing, 0, 0.99)
  const attackSec = 0.03 + smoothDial * 0.16
  const releaseSec = 0.06 + smoothDial * 0.56
  const timeConstant = safeTarget > safeCurrent ? attackSec : releaseSec
  const alpha = 1 - Math.exp(-safeDelta / Math.max(0.0001, timeConstant))
  return safeCurrent * (1 - alpha) + safeTarget * alpha
}

export function updateFlyingGlowWingEnvelope(
  currentPulse: number,
  supportDrive: number,
  triggerDrive: number,
  lastTriggerDrive: number,
  timeSec: number,
  deltaSec: number,
  lastTriggerSec: number,
  beatIntervalSec: number,
  motionSpeed: number,
  releaseControl: number,
): {
  pulseDrive: number
  lastTriggerDrive: number
  lastTriggerSec: number
  beatIntervalSec: number
} {
  const safeCurrentPulse = clamp(Number.isFinite(currentPulse) ? currentPulse : 0, 0, 1)
  const safeSupportDrive = clamp(Number.isFinite(supportDrive) ? supportDrive : 0, 0, 1)
  const safeTriggerDrive = clamp(Number.isFinite(triggerDrive) ? triggerDrive : 0, 0, 1)
  const safeLastTriggerDrive = clamp(Number.isFinite(lastTriggerDrive) ? lastTriggerDrive : 0, 0, 1)
  const safeTimeSec = Number.isFinite(timeSec) ? timeSec : 0
  const safeDeltaSec = clamp(Number.isFinite(deltaSec) ? deltaSec : 1 / 60, 1 / 240, 0.25)
  const safeLastTriggerSec = Number.isFinite(lastTriggerSec) ? lastTriggerSec : -1
  const safeBeatIntervalSec = clamp(Number.isFinite(beatIntervalSec) ? beatIntervalSec : 0.2, 0.07, 0.5)
  const safeMotionSpeed = clamp(Number.isFinite(motionSpeed) ? motionSpeed : 1, 0.5, 20)
  const safeReleaseControl = clamp(Number.isFinite(releaseControl) ? releaseControl : 0.9, 0, 4)
  const normalizedReleaseControl = safeReleaseControl / 4
  const timeSinceLastTrigger =
    safeLastTriggerSec >= 0 ? Math.max(0, safeTimeSec - safeLastTriggerSec) : Number.POSITIVE_INFINITY
  const minTriggerGap = clamp(safeBeatIntervalSec * 0.38, 0.04, 0.16)
  const retriggerCloseThreshold = clamp(0.18 - normalizedReleaseControl * 0.03, 0.12, 0.18)
  const longTimeoutBypass = clamp(
    safeBeatIntervalSec * (1.18 + normalizedReleaseControl * 0.36),
    0.12,
    0.58,
  )
  const retriggerReady =
    safeLastTriggerSec < 0 ||
    safeCurrentPulse <= retriggerCloseThreshold ||
    timeSinceLastTrigger >= longTimeoutBypass
  const risingEdge = safeTriggerDrive > 0.16 && safeTriggerDrive > safeLastTriggerDrive + 0.045
  const strongRetrigger = safeTriggerDrive > 0.6 && timeSinceLastTrigger > minTriggerGap * 0.65
  const crossedThreshold =
    safeTriggerDrive > 0.18 && safeLastTriggerDrive <= 0.12 && timeSinceLastTrigger > minTriggerGap
  const shouldTrigger = retriggerReady && (risingEdge || strongRetrigger || crossedThreshold)

  if (shouldTrigger) {
    const measuredBeatIntervalSec =
      safeLastTriggerSec >= 0 && Number.isFinite(timeSinceLastTrigger)
        ? clamp(timeSinceLastTrigger, 0.07, 0.5)
        : safeBeatIntervalSec
    const nextBeatIntervalSec =
      safeLastTriggerSec >= 0
        ? clamp(safeBeatIntervalSec * 0.68 + measuredBeatIntervalSec * 0.32, 0.07, 0.5)
        : measuredBeatIntervalSec
    const attackSec = clamp((nextBeatIntervalSec * 0.08) / safeMotionSpeed, 0.0015, 0.02)
    const attackAlpha = 1 - Math.exp(-safeDeltaSec / Math.max(0.0001, attackSec))
    const triggerStrength = clamp(0.18 + safeTriggerDrive * 0.82, 0, 1)
    return {
      pulseDrive: safeCurrentPulse * (1 - attackAlpha) + triggerStrength * attackAlpha,
      lastTriggerDrive: safeTriggerDrive,
      lastTriggerSec: safeTimeSec,
      beatIntervalSec: nextBeatIntervalSec,
    }
  }

  const releaseScale =
    0.24 + normalizedReleaseControl * 1.08 + normalizedReleaseControl * normalizedReleaseControl * 0.72
  const releaseSec = clamp((safeBeatIntervalSec * releaseScale) / safeMotionSpeed, 0.002, 0.36)
  const releaseAlpha = 1 - Math.exp(-safeDeltaSec / Math.max(0.0001, releaseSec))
  const sustainFloor = clamp(
    safeSupportDrive * (0.05 + normalizedReleaseControl * 0.08) +
      safeTriggerDrive * (0.04 + normalizedReleaseControl * 0.06),
    0,
    0.18,
  )
  return {
    pulseDrive: safeCurrentPulse * (1 - releaseAlpha) + sustainFloor * releaseAlpha,
    lastTriggerDrive: safeTriggerDrive,
    lastTriggerSec: safeLastTriggerSec,
    beatIntervalSec: safeBeatIntervalSec,
  }
}

export function resolveSpectrumBarCount({
  bounds,
  scale,
  spectrumAttachment,
  spectrumLayers,
  templateDraft,
  resolveAnchorPoint,
}: {
  bounds: SpectrumPreviewBounds
  scale: number
  spectrumAttachment: SpectrumAttachment | null
  spectrumLayers: SpectrumLayerPreview[]
  templateDraft: PreviewSpectrumBarCountDraft
  resolveAnchorPoint: (anchor: string, width: number, height: number) => { x: number; y: number }
}): number {
  const normalizedStyle = normalizeSpectrumStyleKey(templateDraft.style ?? '')
  const solidWingBand =
    (normalizedStyle === 'flying-glow' || normalizedStyle === 'halo-stack') &&
    spectrumLayers.some((layer) => layer.solidBand)
  if (normalizedStyle === 'straight-bars' || normalizedStyle === 'classic-vertical') {
    return getStraightBarsBarCount({
      templateDraft,
      bounds,
      scale,
      spectrumAttachment,
      spectrumLayers,
      resolveAnchorPoint,
    })
  }
  if (solidWingBand) {
    return normalizedStyle === 'flying-glow' ? 220 : 180
  }
  return getSpectrumBarCount(normalizedStyle)
}
