import type { PreviewBackgroundPresentationDraft } from '@/features/video/core/contracts/previewDraftContracts'
import { clamp } from '@/features/video/preview/previewUtils'

export type BackgroundPresentationState = {
  objectFit: 'cover' | 'contain'
  brightness: number
  translateX: number
  translateY: number
  scale: number
  drawX: number
  drawY: number
  drawWidth: number
  drawHeight: number
}

function smoothstep01(value: number): number {
  const unit = clamp(value, 0, 1)
  return unit * unit * (3 - 2 * unit)
}

function resolveLocalPulseEnergy(
  value: number,
  threshold: number,
  width: number,
  curve = 1,
): number {
  const normalized = smoothstep01((clamp(value, 0, 1) - threshold) / Math.max(0.0001, width))
  return clamp(Math.pow(normalized, curve), 0, 1)
}

export function resolveBackgroundPresentationState(
  draft: PreviewBackgroundPresentationDraft,
  width: number,
  height: number,
  imageWidth: number,
  imageHeight: number,
  reactiveEnergy: number,
  timeSec: number,
): BackgroundPresentationState {
  const safeWidth = Math.max(1, width)
  const safeHeight = Math.max(1, height)
  const safeImageWidth = Math.max(1, imageWidth)
  const safeImageHeight = Math.max(1, imageHeight)
  const safeReactiveEnergy = clamp(reactiveEnergy, 0, 1)
  const baseScale =
    draft.backgroundFitMode === 'contain'
      ? Math.min(safeWidth / safeImageWidth, safeHeight / safeImageHeight)
      : Math.max(safeWidth / safeImageWidth, safeHeight / safeImageHeight)
  const reactivityDial = clamp(draft.backgroundReactivity, 0, 20)
  const zoomDial = clamp(draft.backgroundMotionZoomStrength, 0, 20)
  const vibrateDial = clamp(draft.backgroundMotionVibrateStrength, 0, 20)
  
  // Audio reactivity is master gain for music reaction
  const audioReactionStrength = safeReactiveEnergy * (0.8 + reactivityDial * 0.25)
  // Zoom/vibrate strength control magnitude of each effect
  const zoomAmplitude =
    draft.backgroundMotionMode === 'zoom' || draft.backgroundMotionMode === 'both'
      ? (zoomDial * 0.06 + 0.03) * audioReactionStrength
      : 0
  const vibrateStrength =
    draft.backgroundMotionMode === 'vibrate' || draft.backgroundMotionMode === 'both'
      ? (vibrateDial * 1.5 + 0.8) * audioReactionStrength
      : 0
  // Motion speed controls how fast the animations cycle
  const motionSpeed = clamp(draft.backgroundMotionSpeed, 0, 20)
  const animationSpeed = 0.5 + motionSpeed * 0.5
  
  const translateX = vibrateStrength > 0 ? Math.sin(timeSec * 8.2 * animationSpeed) * vibrateStrength : 0
  const translateY = vibrateStrength > 0 ? Math.cos(timeSec * 7.4 * animationSpeed) * vibrateStrength * 0.55 : 0
  const zoomAmount = zoomAmplitude > 0 ? (Math.sin(timeSec * 6.0 * animationSpeed) + 1) / 2 * zoomAmplitude : 0
  const scale = Math.max(0.25, draft.backgroundUserScale + zoomAmount)
  const drawScale = Math.max(0.25, (baseScale || 1) * scale)
  const drawWidth = safeImageWidth * drawScale
  const drawHeight = safeImageHeight * drawScale

  return {
    objectFit: draft.backgroundFitMode === 'contain' ? 'contain' : 'cover',
    brightness: Math.max(0.1, draft.backgroundBrightness),
    translateX,
    translateY,
    scale,
    drawX: (safeWidth - drawWidth) * 0.5 + translateX,
    drawY: (safeHeight - drawHeight) * 0.5 + translateY,
    drawWidth,
    drawHeight,
  }
}

export function resolveBackgroundReactiveDriveEnergy(
  smoothedBackgroundEnergy: number,
  beatDelta: number,
  kick: number,
  drop: number,
): number {
  const sustain = clamp(smoothedBackgroundEnergy, 0, 1) * 0.03
  const onsetPulse = resolveLocalPulseEnergy(beatDelta, 0.05, 0.16, 1.12) * 0.94
  const kickPulse = resolveLocalPulseEnergy(kick, 0.11, 0.16, 1.04) * 0.82
  const dropPulse = resolveLocalPulseEnergy(drop, 0.15, 0.2, 1.08) * 0.48
  return clamp(Math.max(sustain, onsetPulse, kickPulse, dropPulse), 0, 1)
}
