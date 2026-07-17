import type { AudioAnalysisRuntime } from '@/features/video/preview/audioFeatureBus'
import { resolvePreviewPlaybackReport } from '@/features/video/preview/previewFrameState'
import { buildPreviewPlaybackState } from '@/features/video/preview/transportClock'
import type { VideoWorkspaceState } from '@/shared/types/desktop'

type ApplyPreviewPlaybackReportOptions = {
  runtime: AudioAnalysisRuntime
  timestamp: number
  lastReportedAt: number
  reportPlaybackState: (nextState: VideoWorkspaceState['playback'], force?: boolean) => void
}

export type ApplyPreviewPlaybackReportResult = {
  nextReportedAt: number
  didReport: boolean
}

export function applyPreviewPlaybackReport({
  runtime,
  timestamp,
  lastReportedAt,
  reportPlaybackState,
}: ApplyPreviewPlaybackReportOptions): ApplyPreviewPlaybackReportResult {
  const playbackReport = resolvePreviewPlaybackReport({
    runtime,
    timestamp,
    lastReportedAt,
  })

  if (playbackReport.shouldReport && runtime.audioElement) {
    reportPlaybackState(buildPreviewPlaybackState(runtime.audioElement))
  }

  return {
    nextReportedAt: playbackReport.nextReportedAt,
    didReport: playbackReport.shouldReport,
  }
}
