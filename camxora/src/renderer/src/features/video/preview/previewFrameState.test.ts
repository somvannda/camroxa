import {
  resolvePreviewFrameState,
  resolvePreviewPlaybackReport,
} from '@/features/video/preview/previewFrameState'

describe('resolvePreviewFrameState', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('resolves layout, dpr, center point, and frame timing', () => {
    vi.spyOn(window, 'devicePixelRatio', 'get').mockReturnValue(2)

    const result = resolvePreviewFrameState({
      bounds: { width: 1280, height: 720 },
      scale: 1.5,
      spectrumAttachment: {
        attachedToLogo: true,
        baseRadius: 120,
        centerOffsetX: 10,
        centerOffsetY: -6,
      },
      positionDraft: {
        anchor: 'bottom-center',
        positionX: 20,
        positionY: -10,
      } as never,
      qualityPolicy: {
        tier: 'balanced',
        maxDpr: 1.5,
        maxRenderPixels: 2200000,
      } as never,
      timestamp: 2016,
      previousTimestamp: 2000,
      resolveAnchorPoint: vi.fn().mockReturnValue({ x: 640, y: 360 }),
    })

    expect(result.logicalWidth).toBe(1280)
    expect(result.logicalHeight).toBe(720)
    expect(result.dpr).toBeLessThanOrEqual(1.5)
    expect(result.centerX).toBe(680)
    expect(result.centerY).toBe(339)
    expect(result.deltaSec).toBeCloseTo(0.016, 5)
    expect(result.timeSec).toBe(2.016)
  })

  it('clamps delta time to a small positive minimum', () => {
    vi.spyOn(window, 'devicePixelRatio', 'get').mockReturnValue(1)

    const result = resolvePreviewFrameState({
      bounds: { width: 640, height: 360 },
      scale: 1,
      spectrumAttachment: null,
      positionDraft: {
        anchor: 'center',
        positionX: 0,
        positionY: 0,
      } as never,
      qualityPolicy: {
        tier: 'compatibility',
        maxDpr: 1.25,
        maxRenderPixels: 1600000,
      } as never,
      timestamp: 1000,
      previousTimestamp: 1000,
      resolveAnchorPoint: vi.fn().mockReturnValue({ x: 320, y: 180 }),
    })

    expect(result.deltaSec).toBe(0.001)
  })

  it('caps oversized frame deltas so interaction stalls do not spike simulation time', () => {
    vi.spyOn(window, 'devicePixelRatio', 'get').mockReturnValue(1)

    const result = resolvePreviewFrameState({
      bounds: { width: 640, height: 360 },
      scale: 1,
      spectrumAttachment: null,
      positionDraft: {
        anchor: 'center',
        positionX: 0,
        positionY: 0,
      } as never,
      qualityPolicy: {
        tier: 'compatibility',
        maxDpr: 1.25,
        maxRenderPixels: 1600000,
      } as never,
      timestamp: 1200,
      previousTimestamp: 1000,
      resolveAnchorPoint: vi.fn().mockReturnValue({ x: 320, y: 180 }),
    })

    expect(result.deltaSec).toBe(0.05)
  })

  it('keeps a higher preview dpr floor for sharp flying glow edges', () => {
    vi.spyOn(window, 'devicePixelRatio', 'get').mockReturnValue(2)

    const result = resolvePreviewFrameState({
      bounds: { width: 1920, height: 1080 },
      preferSharpSpectrumEdges: true,
      scale: 1,
      spectrumAttachment: null,
      positionDraft: {
        anchor: 'center',
        positionX: 0,
        positionY: 0,
      } as never,
      qualityPolicy: {
        tier: 'compatibility',
        maxDpr: 1.25,
        maxRenderPixels: 1600000,
      } as never,
      timestamp: 1200,
      previousTimestamp: 1000,
      resolveAnchorPoint: vi.fn().mockReturnValue({ x: 960, y: 540 }),
    })

    expect(result.dpr).toBe(1.25)
  })
})

describe('resolvePreviewPlaybackReport', () => {
  it('requests a playback report only after the report interval', () => {
    const runtime = {
      audioElement: { paused: false },
    } as never

    expect(
      resolvePreviewPlaybackReport({
        runtime,
        timestamp: 150,
        lastReportedAt: 80,
      }),
    ).toEqual({
      shouldReport: false,
      nextReportedAt: 80,
    })

    expect(
      resolvePreviewPlaybackReport({
        runtime,
        timestamp: 160,
        lastReportedAt: 80,
      }),
    ).toEqual({
      shouldReport: true,
      nextReportedAt: 160,
    })
  })

  it('does not report when no audio element is bound', () => {
    expect(
      resolvePreviewPlaybackReport({
        runtime: {
          audioElement: null,
        } as never,
        timestamp: 200,
        lastReportedAt: 100,
      }),
    ).toEqual({
      shouldReport: false,
      nextReportedAt: 100,
    })
  })
})
