import { applyPreviewPlaybackReport } from '@/features/video/preview/previewPlaybackReporter'

const resolvePreviewPlaybackReportMock = vi.fn()
const buildPreviewPlaybackStateMock = vi.fn()

vi.mock('@/features/video/preview/previewFrameState', () => ({
  resolvePreviewPlaybackReport: (...args: unknown[]) => resolvePreviewPlaybackReportMock(...args),
}))

vi.mock('@/features/video/preview/transportClock', () => ({
  buildPreviewPlaybackState: (...args: unknown[]) => buildPreviewPlaybackStateMock(...args),
}))

describe('applyPreviewPlaybackReport', () => {
  beforeEach(() => {
    resolvePreviewPlaybackReportMock.mockReset()
    buildPreviewPlaybackStateMock.mockReset()
  })

  it('reports playback when cadence allows it and an audio element is present', () => {
    const reportPlaybackState = vi.fn()
    const audioElement = { paused: false }

    resolvePreviewPlaybackReportMock.mockReturnValue({
      shouldReport: true,
      nextReportedAt: 2400,
    })
    buildPreviewPlaybackStateMock.mockReturnValue({
      isPlaying: true,
      isReady: true,
      isLoading: false,
      currentTimeSec: 1.5,
      durationSec: 12,
    })

    const result = applyPreviewPlaybackReport({
      runtime: { audioElement } as never,
      timestamp: 2400,
      lastReportedAt: 2200,
      reportPlaybackState,
    })

    expect(resolvePreviewPlaybackReportMock).toHaveBeenCalledWith({
      runtime: { audioElement },
      timestamp: 2400,
      lastReportedAt: 2200,
    })
    expect(buildPreviewPlaybackStateMock).toHaveBeenCalledWith(audioElement)
    expect(reportPlaybackState).toHaveBeenCalledWith(
      expect.objectContaining({
        isPlaying: true,
      }),
    )
    expect(result).toEqual({
      nextReportedAt: 2400,
      didReport: true,
    })
  })

  it('skips reporting when cadence blocks the update', () => {
    const reportPlaybackState = vi.fn()

    resolvePreviewPlaybackReportMock.mockReturnValue({
      shouldReport: false,
      nextReportedAt: 2200,
    })

    const result = applyPreviewPlaybackReport({
      runtime: { audioElement: { paused: true } } as never,
      timestamp: 2250,
      lastReportedAt: 2200,
      reportPlaybackState,
    })

    expect(buildPreviewPlaybackStateMock).not.toHaveBeenCalled()
    expect(reportPlaybackState).not.toHaveBeenCalled()
    expect(result).toEqual({
      nextReportedAt: 2200,
      didReport: false,
    })
  })
})
