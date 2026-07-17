import type { PreviewFramePositionDraft } from '@/features/video/core/contracts/previewDraftContracts'
import type { AudioAnalysisRuntime } from '@/features/video/preview/audioFeatureBus'
import { clampPreviewDpr, type PreviewQualityPolicy } from '@/features/video/preview/previewQualityPolicy'
import type { SpectrumAttachment } from '@/features/video/core/scene/attachmentService'

export type PreviewFrameState = {
  logicalWidth: number
  logicalHeight: number
  dpr: number
  centerX: number
  centerY: number
  deltaSec: number
  timeSec: number
}

type ResolvePreviewFrameStateOptions = {
  bounds: {
    width: number
    height: number
  }
  preferSharpSpectrumEdges?: boolean
  scale: number
  spectrumAttachment: SpectrumAttachment | null
  positionDraft: PreviewFramePositionDraft
  qualityPolicy: PreviewQualityPolicy
  timestamp: number
  previousTimestamp: number
  resolveAnchorPoint: (anchor: string, width: number, height: number) => { x: number; y: number }
}

type ResolvePreviewPlaybackReportOptions = {
  runtime: AudioAnalysisRuntime
  timestamp: number
  lastReportedAt: number
  intervalMs?: number
}

export function resolvePreviewFrameState({
  bounds,
  preferSharpSpectrumEdges = false,
  scale,
  spectrumAttachment,
  positionDraft,
  qualityPolicy,
  timestamp,
  previousTimestamp,
  resolveAnchorPoint,
}: ResolvePreviewFrameStateOptions): PreviewFrameState {
  const baseDpr = window.devicePixelRatio || 1
  const logicalWidth = Math.max(1, bounds.width)
  const logicalHeight = Math.max(1, bounds.height)
  const clampedDpr = clampPreviewDpr(baseDpr, logicalWidth, logicalHeight, qualityPolicy)
  const sharpEdgeDprFloor = preferSharpSpectrumEdges
    ? Math.min(
        qualityPolicy.maxDpr,
        baseDpr >= 1.25 ? 1.25 : 1,
      )
    : 0
  const dpr = Math.max(clampedDpr, sharpEdgeDprFloor)

  const anchorPoint = resolveAnchorPoint(positionDraft.anchor, logicalWidth, logicalHeight)
  const centerX =
    anchorPoint.x + positionDraft.positionX * scale + (spectrumAttachment?.centerOffsetX ?? 0)
  const centerY =
    anchorPoint.y + positionDraft.positionY * scale + (spectrumAttachment?.centerOffsetY ?? 0)

  return {
    logicalWidth,
    logicalHeight,
    dpr,
    centerX,
    centerY,
    deltaSec: Math.min(0.05, Math.max(0.001, (timestamp - previousTimestamp) / 1000)),
    timeSec: timestamp / 1000,
  }
}

export function resolvePreviewPlaybackReport({
  runtime,
  timestamp,
  lastReportedAt,
  intervalMs = 80,
}: ResolvePreviewPlaybackReportOptions): {
  shouldReport: boolean
  nextReportedAt: number
} {
  const shouldReport = Boolean(
    runtime.audioElement && timestamp - lastReportedAt >= intervalMs,
  )

  return {
    shouldReport,
    nextReportedAt: shouldReport ? timestamp : lastReportedAt,
  }
}
