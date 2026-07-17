import type { PreviewLogoPresentationDraft } from '@/features/video/core/contracts/previewDraftContracts'
import { clamp } from '@/features/video/preview/previewUtils'

export type LogoPresentationState = {
  x: number
  y: number
  size: number
  centerX: number
  centerY: number
  rotationRad: number
  rotationDeg: number
  opacity: number
  borderRadiusPx: number
  outlineAlpha: number
  glowAlpha: number
  depthAlpha: number
  shadowBlurPx: number
  shadowOffsetYPx: number
}

function smoothstep01(value: number): number {
  const unit = clamp(value, 0, 1)
  return unit * unit * (3 - 2 * unit)
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





export function resolveLogoReactiveDriveEnergy(
  smoothedLogoEnergy: number,
  beatDelta: number,
  kick: number,
  drop: number,
): number {
  const sustain = clamp(smoothedLogoEnergy, 0, 1) * 0.04
  const onsetPulse = smoothstep01(clamp(beatDelta, 0, 1) / 0.018)
  const kickPulse = smoothstep01(clamp(kick, 0, 1.2) / 0.1) * 0.92
  const dropPulse = smoothstep01(clamp(drop, 0, 1.2) / 0.14) * 0.72
  return clamp(Math.max(sustain, onsetPulse, kickPulse, dropPulse), 0, 1)
}

export function resolveLogoPresentationState(
  draft: PreviewLogoPresentationDraft,
  width: number,
  height: number,
  scale: number,
  reactiveEnergy: number,
  timeSec: number,
): LogoPresentationState {
  const safeReactiveEnergy = clamp(reactiveEnergy, 0, 1)
  const baseSize = Math.max(32, draft.logoSizeStep * 100 * scale)
  const reactivityDial = clamp(draft.logoReactivity, 0, 2)
  // Revamped: simpler, more responsive logo pulse
  const pulseStrength = safeReactiveEnergy * (1.8 + reactivityDial * 0.12)
  const pulseAmplitude = 0.15 + reactivityDial * 0.08
  const pulse = 1 + pulseStrength * pulseAmplitude
  
  // Logo motion controls
  const motionMode = draft.logoMotionMode || 'none'
  const zoomDial = clamp(draft.logoMotionZoomStrength, 0, 20)
  const vibrateDial = clamp(draft.logoMotionVibrateStrength, 0, 20)
  const motionSpeed = clamp(draft.logoMotionSpeed, 0, 20)
  const animationSpeed = 0.5 + motionSpeed * 0.5
  
  const zoomAmplitude = (motionMode === 'zoom' || motionMode === 'both') ? (zoomDial * 0.02 + 0.01) * pulseStrength : 0
  const zoomAmount = zoomAmplitude > 0 ? (Math.sin(timeSec * 6.0 * animationSpeed) + 1) / 2 * zoomAmplitude : 0
  const size = baseSize * pulse * (1 + zoomAmount)
  
  const vibrateStrength = (motionMode === 'vibrate' || motionMode === 'both') ? (vibrateDial * 0.8 + 0.4) * pulseStrength * scale : 0
  const translateX = vibrateStrength > 0 ? Math.sin(timeSec * 8.2 * animationSpeed) * vibrateStrength : 0
  const translateY = vibrateStrength > 0 ? Math.cos(timeSec * 7.4 * animationSpeed) * vibrateStrength * 0.55 : 0
  
  const rect = resolveAnchoredRect(
    draft.anchor,
    draft.positionX * scale + translateX,
    draft.positionY * scale + translateY,
    size,
    size,
    width,
    height,
  )
  const spinDirection = String(draft.logoSpinDirection || 'cw').trim().toLowerCase() === 'ccw' ? -1 : 1
  const rotationRad =
    draft.logoSpinEnabled && draft.logoSpinSpeed > 0 ? timeSec * draft.logoSpinSpeed * 0.35 * spinDirection : 0

  return {
    x: rect.x,
    y: rect.y,
    size,
    centerX: rect.x + size * 0.5,
    centerY: rect.y + size * 0.5,
    rotationRad,
    rotationDeg: (rotationRad * 180) / Math.PI,
    opacity: clamp(draft.logoOpacity, 0, 1),
    borderRadiusPx: draft.logoShape === 'circle' ? 9999 : Math.max(8, size * 0.18),
    outlineAlpha: 0.12,
    glowAlpha: draft.logoSpinEnabled ? 0.11 : 0.08,
    depthAlpha: 0.18,
    shadowBlurPx: Math.max(16, baseSize * 0.14),
    shadowOffsetYPx: Math.max(6, baseSize * 0.08),
  }
}
