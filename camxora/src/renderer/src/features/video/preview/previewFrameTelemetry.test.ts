import { createPreviewFrameTelemetry } from '@/features/video/preview/previewFrameTelemetry'

describe('createPreviewFrameTelemetry', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('aggregates timings and emits a rounded report at the reporting interval', () => {
    vi.spyOn(performance, 'now').mockReturnValue(0)
    const send = vi.fn()
    const telemetry = createPreviewFrameTelemetry({
      send,
      reportIntervalMs: 1000,
    })

    telemetry.recordTiming('layout', 3)
    telemetry.recordTiming('audio', 4)
    telemetry.recordTiming('spectrum', 5)
    telemetry.recordTiming('instances', 6)
    telemetry.recordTiming('particles', 7)
    telemetry.recordTiming('canvas2d', 8)
    telemetry.recordTiming('render', 9)
    telemetry.recordFrame(20)

    telemetry.recordTiming('layout', 1)
    telemetry.recordTiming('audio', 2)
    telemetry.recordTiming('spectrum', 3)
    telemetry.recordTiming('instances', 4)
    telemetry.recordTiming('particles', 5)
    telemetry.recordTiming('canvas2d', 6)
    telemetry.recordTiming('render', 7)
    telemetry.recordFrame(10)

    telemetry.reportFrame(1000, {
      dpr: 1.5,
      width: 1280,
      height: 720,
      barCount: 96,
      layerCount: 2,
      qualityTier: 'balanced',
      adaptiveQualityLevel: 1,
      performanceScene: 'heavy-bloom',
      instanceCount: 240,
      particleCount: 180,
      useWebGpuSpectrum: true,
      showDomPreviewBackground: false,
      showDomPreviewLogo: true,
      postFx: true,
    })

    expect(send).toHaveBeenCalledWith({
      frames: 2,
      avgFrameMs: 15,
      maxFrameMs: 20,
      layoutAvgMs: 2,
      audioAvgMs: 3,
      spectrumAvgMs: 4,
      instancesAvgMs: 5,
      particlesAvgMs: 6,
      canvas2dAvgMs: 7,
      renderAvgMs: 8,
      dpr: 1.5,
      width: 1280,
      height: 720,
      barCount: 96,
      layerCount: 2,
      qualityTier: 'balanced',
      adaptiveQualityLevel: 1,
      performanceScene: 'heavy-bloom',
      instanceCount: 240,
      particleCount: 180,
      useWebGpuSpectrum: true,
      showDomPreviewBackground: false,
      showDomPreviewLogo: true,
      postFx: true,
    })
  })

  it('does not emit before the interval and resets after reporting', () => {
    vi.spyOn(performance, 'now').mockReturnValue(0)
    const send = vi.fn()
    const telemetry = createPreviewFrameTelemetry({
      send,
      reportIntervalMs: 1000,
    })

    telemetry.recordTiming('layout', 5)
    telemetry.recordFrame(12)
    telemetry.reportFrame(900, {
      dpr: 1,
      width: 640,
      height: 360,
      barCount: 32,
      layerCount: 1,
      qualityTier: 'compatibility',
      adaptiveQualityLevel: 0,
      performanceScene: 'baseline',
      instanceCount: 40,
      particleCount: 30,
      useWebGpuSpectrum: false,
      showDomPreviewBackground: true,
      showDomPreviewLogo: false,
      postFx: false,
    })

    expect(send).not.toHaveBeenCalled()

    telemetry.reportFrame(1000, {
      dpr: 1,
      width: 640,
      height: 360,
      barCount: 32,
      layerCount: 1,
      qualityTier: 'compatibility',
      adaptiveQualityLevel: 0,
      performanceScene: 'baseline',
      instanceCount: 40,
      particleCount: 30,
      useWebGpuSpectrum: false,
      showDomPreviewBackground: true,
      showDomPreviewLogo: false,
      postFx: false,
    })

    telemetry.recordTiming('layout', 1)
    telemetry.recordFrame(6)
    telemetry.reportFrame(2000, {
      dpr: 2,
      width: 800,
      height: 600,
      barCount: 64,
      layerCount: 3,
      qualityTier: 'performance',
      adaptiveQualityLevel: 2,
      performanceScene: 'max-layers',
      instanceCount: 100,
      particleCount: 70,
      useWebGpuSpectrum: true,
      showDomPreviewBackground: false,
      showDomPreviewLogo: false,
      postFx: true,
    })

    expect(send).toHaveBeenNthCalledWith(
      1,
      expect.objectContaining({
        frames: 1,
        avgFrameMs: 12,
        layoutAvgMs: 5,
        width: 640,
        performanceScene: 'baseline',
      }),
    )
    expect(send).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({
        frames: 1,
        avgFrameMs: 6,
        layoutAvgMs: 1,
        width: 800,
        performanceScene: 'max-layers',
      }),
    )
  })
})
