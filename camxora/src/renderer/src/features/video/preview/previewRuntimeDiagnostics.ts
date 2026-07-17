import {
  createPreviewFrameTelemetry,
  type PreviewFrameTelemetry,
  type PreviewFrameTelemetryReport,
} from '@/features/video/preview/previewFrameTelemetry'
import { createVideoDebugSender } from '@/features/video/videoDiagnostics'

type CreatePreviewRuntimeDiagnosticsOptions = {
  onReport?: (report: PreviewFrameTelemetryReport) => void
}

export function createPreviewRuntimeDiagnostics({
  onReport,
}: CreatePreviewRuntimeDiagnosticsOptions = {}): {
  telemetry: PreviewFrameTelemetry
} {
  const debugSend = createVideoDebugSender({
    sessionId: 'preview-slow-performance',
    runId: 'post-fix',
  })

  const telemetry = createPreviewFrameTelemetry({
    send: (report) => {
      debugSend({
        hypothesisId: 'A',
        location: 'usePreviewRuntime:renderFrame',
        msg: '[DEBUG] preview frame timing sample',
        data: report,
      })
      onReport?.(report)
    },
  })

  return {
    telemetry,
  }
}
