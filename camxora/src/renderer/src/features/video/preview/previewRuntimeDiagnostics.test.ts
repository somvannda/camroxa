import { createPreviewRuntimeDiagnostics } from '@/features/video/preview/previewRuntimeDiagnostics'

const createVideoDebugSenderMock = vi.fn()
const createPreviewFrameTelemetryMock = vi.fn()

vi.mock('@/features/video/videoDiagnostics', () => ({
  createVideoDebugSender: (...args: unknown[]) => createVideoDebugSenderMock(...args),
}))

vi.mock('@/features/video/preview/previewFrameTelemetry', () => ({
  createPreviewFrameTelemetry: (...args: unknown[]) => createPreviewFrameTelemetryMock(...args),
}))

describe('createPreviewRuntimeDiagnostics', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('creates preview telemetry with the shared debug sender envelope', () => {
    const debugSend = vi.fn()
    const telemetry = { reportFrame: vi.fn(), recordFrame: vi.fn(), recordTiming: vi.fn() }
    const onReport = vi.fn()
    const report = { frames: 12, avgFrameMs: 16.4 }

    createVideoDebugSenderMock.mockReturnValue(debugSend)
    createPreviewFrameTelemetryMock.mockImplementation(({ send }) => {
      send(report)
      return telemetry
    })

    const result = createPreviewRuntimeDiagnostics({
      onReport,
    })

    expect(createVideoDebugSenderMock).toHaveBeenCalledWith({
      sessionId: 'preview-slow-performance',
      runId: 'post-fix',
    })
    expect(createPreviewFrameTelemetryMock).toHaveBeenCalledWith({
      send: expect.any(Function),
    })
    expect(debugSend).toHaveBeenCalledWith({
      hypothesisId: 'A',
      location: 'usePreviewRuntime:renderFrame',
      msg: '[DEBUG] preview frame timing sample',
      data: report,
    })
    expect(onReport).toHaveBeenCalledWith(report)
    expect(result).toEqual({ telemetry })
  })
})
