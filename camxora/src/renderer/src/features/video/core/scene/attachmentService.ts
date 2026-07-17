import type { PreviewSpectrumAttachmentDraft } from '@/features/video/core/contracts/previewDraftContracts'
import type { SpectrumLayerPreview } from '@/features/video/domains/spectrum/spectrumLayerModel'
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

export type SpectrumAttachment = {
  centerOffsetX: number
  centerOffsetY: number
  baseRadius: number
  attachedToLogo: boolean
}

export function computeLogoOuterRadius(
  draft: PreviewSpectrumAttachmentDraft,
  scale: number,
  visibleRadiusRatio: number,
  logoPresentationState: LogoPresentationState | null,
): number {
  if (logoPresentationState) {
    // Use dynamic size from logo presentation state
    return logoPresentationState.size * 0.5 * clamp(visibleRadiusRatio, 0.2, 1)
  }
  const baseSize = Math.max(32, draft.logoSizeStep * 100 * scale)
  return baseSize * 0.5 * clamp(visibleRadiusRatio, 0.2, 1)
}

export function resolveSpectrumAttachment(
  draft: PreviewSpectrumAttachmentDraft,
  spectrumLayers: readonly SpectrumLayerPreview[],
  scale: number,
  logoVisibleRadiusRatio: number,
  logoPresentationState: LogoPresentationState | null,
): SpectrumAttachment {
  const logoVisible = draft.logoEnabled && draft.logoPath.trim().length > 0
  const attachedToLogo = logoVisible && draft.spectrumAttachToLogo
  const logoOuterRadius = computeLogoOuterRadius(draft, scale, logoVisibleRadiusRatio, logoPresentationState)
  const furthestGap = spectrumLayers.reduce((maxValue, layer) => Math.max(maxValue, layer.radiusOffset), 0)
  const outerPadding = attachedToLogo ? Math.max(0, draft.spectrumLogoGap * scale) : 0
  const baseRadius = attachedToLogo
    ? logoOuterRadius + outerPadding
    : Math.max(72 * scale, furthestGap * scale * 0.28)

  // If attached to logo, use dynamic logo center!
  const centerOffsetX = (attachedToLogo && logoPresentationState ? logoPresentationState.centerX : 0)
  const centerOffsetY = (attachedToLogo && logoPresentationState ? logoPresentationState.centerY : 0)

  return {
    centerOffsetX,
    centerOffsetY,
    baseRadius,
    attachedToLogo,
  }
}
