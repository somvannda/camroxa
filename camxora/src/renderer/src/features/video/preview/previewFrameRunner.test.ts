import { runPreviewFrame } from '@/features/video/preview/previewFrameRunner'

const applyPreviewPlaybackReportMock = vi.fn()
const applyPreviewFrameReportMock = vi.fn()
const resolvePreviewFrameStateMock = vi.fn()
const resolvePreviewReactiveFrameStateMock = vi.fn()
const renderPreviewDomFrameMock = vi.fn()
const runPreviewGpuRuntimeCoordinatorMock = vi.fn()

vi.mock('@/features/video/preview/previewPlaybackReporter', () => ({
  applyPreviewPlaybackReport: (...args: unknown[]) => applyPreviewPlaybackReportMock(...args),
}))

vi.mock('@/features/video/preview/previewFrameReporter', () => ({
  applyPreviewFrameReport: (...args: unknown[]) => applyPreviewFrameReportMock(...args),
}))

vi.mock('@/features/video/preview/previewFrameState', () => ({
  resolvePreviewFrameState: (...args: unknown[]) => resolvePreviewFrameStateMock(...args),
}))

vi.mock('@/features/video/preview/previewReactiveFrameState', () => ({
  resolvePreviewReactiveFrameState: (...args: unknown[]) =>
    resolvePreviewReactiveFrameStateMock(...args),
}))

vi.mock('@/features/video/preview/previewDomFrameRenderer', () => ({
  renderPreviewDomFrame: (...args: unknown[]) => renderPreviewDomFrameMock(...args),
}))

vi.mock('@/features/video/preview/previewGpuRuntimeCoordinator', () => ({
  runPreviewGpuRuntimeCoordinator: (...args: unknown[]) =>
    runPreviewGpuRuntimeCoordinatorMock(...args),
}))

describe('runPreviewFrame', () => {
  beforeEach(() => {
    vi.restoreAllMocks()

    runPreviewGpuRuntimeCoordinatorMock.mockReset()
    resolvePreviewFrameStateMock.mockReturnValue({
      logicalWidth: 1280,
      logicalHeight: 720,
      dpr: 1.25,
      centerX: 640,
      centerY: 360,
      deltaSec: 0.016,
      timeSec: 2.4,
    })
    applyPreviewPlaybackReportMock.mockReturnValue({
      didReport: true,
      nextReportedAt: 2400,
    })
    applyPreviewFrameReportMock.mockReset()
    resolvePreviewReactiveFrameStateMock.mockReturnValue({
      analysedFrame: { levels: [] },
      hasBoundAudio: true,
      reactiveEnergy: 0.7,
      timing: {
        audioMs: 1.2,
        spectrumMs: 2.3,
      },
    })
    renderPreviewDomFrameMock.mockReturnValue({
      backdropSource: 'backdrop-source',
      overlaySource: 'overlay-source',
    })
    runPreviewGpuRuntimeCoordinatorMock.mockReturnValue({
      gpuInstances: [{ id: 'i1' }, { id: 'i2' }],
      gpuParticles: [{ id: 'p1' }],
      hasPostFx: true,
      timing: {
        instancesMs: 3.1,
        particlesMs: 4.2,
        renderMs: 5.3,
      },
    })
  })

  it('coordinates frame helpers, telemetry, and playback reporting', () => {
    const recordTiming = vi.fn()
    const recordFrame = vi.fn()
    const reportFrame = vi.fn()
    const reportPlaybackState = vi.fn()

    runPreviewFrame({
      frame: {
        timestamp: 2400,
        previousTimestamp: 2384,
      },
      scene: {
        viewport: {
          bounds: { width: 1280, height: 720 },
          scale: 1,
          backgroundSrc: 'blob:bg',
          logoSrc: 'blob:logo',
          showFallbackScene: false,
          showDomPreviewBackground: true,
          showDomPreviewLogo: true,
          webgpuReady: true,
        },
        gpuNode: {
          atmosphereEnabled: true,
          submitFallbackScene: false,
          submitSpectrumInstances: true,
        },
        runtimeNode: {
          positionDraft: {
            anchor: 'bottom-center',
            positionX: 0,
            positionY: 0,
          },
          reactiveDraft: {} as never,
          gpuDrafts: {} as never,
          presentationDraft: {} as never,
        },
        transport: {
          currentPlaybackTimeSec: 0,
          selectedMp3Path: 'D:/song.mp3',
          playback: { isReady: true },
        },
        capability: {
          label: 'WebGPU',
          message: 'Ready',
        },
        quality: {
          capabilityProfile: {
            rendererCapability: 'webgpu',
          },
          policy: {
            tier: 'balanced',
            adaptiveQualityLevel: 0,
          },
        },
        performance: {
          primaryScene: 'heavy-bloom',
        },
        backgroundNode: {
          src: 'blob:bg',
          loadStatus: 'ready',
          domStyle: {},
        },
        logoNode: {
          enabled: true,
          src: 'blob:logo',
          loadStatus: 'ready',
          visibleRadiusRatio: 0.8,
          domStyle: {},
        },
        spectrumNode: {
          enabled: true,
          style: 'straight-bars',
          layers: [{ id: 'layer-1' }],
          attachment: null,
          barCount: 96,
          flyingGlowWingRelease: 0.8,
        },
        particlesNode: {
          enabled: true,
        },
        textNodes: {
          active: [{ key: 'title' }],
          enabledCount: 1,
        },
        statusBadges: [],
      } as never,
      audioRuntimeRef: {
        current: {
          audioElement: { paused: false },
        },
      } as never,
      lastPlaybackReportAtRef: { current: 2200 },
      previewMotionRef: { current: { backgroundEnergy: 0 } } as never,
      particleStateRef: { current: { particles: [] } } as never,
      telemetry: {
        recordTiming,
        recordFrame,
        reportFrame,
      },
      reportPlaybackState,
      resolveAnchorPoint: vi.fn().mockReturnValue({ x: 640, y: 360 }),
      averageValues: vi.fn().mockReturnValue(0.3),
      buildLayerSpectrumValues: vi.fn().mockReturnValue([0.2, 0.4]),
      buildSyntheticSpectrumValues: vi.fn().mockReturnValue([0.1, 0.2]),
      smoothPreviewReactiveValue: vi.fn((current: number, target: number) => current + (target - current)),
      updateFlyingGlowWingEnvelope: vi.fn(),
      backdropCanvasRef: { current: null },
      backgroundImageRef: { current: null },
      domBackgroundImageRef: { current: null },
      domLogoLayerRef: { current: null },
      drawBackgroundLayer: vi.fn(),
      drawLogoLayer: vi.fn(),
      drawTextOverlays: vi.fn(),
      logoImageRef: { current: null },
      overlayCanvasRef: { current: null },
      applyDomBackgroundPresentation: vi.fn(),
      applyDomLogoPresentation: vi.fn(),
      webgpuRendererRef: { current: null },
    })

    expect(resolvePreviewFrameStateMock).toHaveBeenCalled()
    expect(applyPreviewPlaybackReportMock).toHaveBeenCalledWith({
      runtime: { audioElement: { paused: false } },
      timestamp: 2400,
      lastReportedAt: 2200,
      reportPlaybackState,
    })
    expect(renderPreviewDomFrameMock).toHaveBeenCalled()
    expect(runPreviewGpuRuntimeCoordinatorMock).toHaveBeenCalledWith(
      expect.objectContaining({
        backdropSource: 'backdrop-source',
        gpuNode: {
          atmosphereEnabled: true,
          submitFallbackScene: false,
          submitSpectrumInstances: true,
        },
        overlaySource: 'overlay-source',
        logicalWidth: 1280,
        logicalHeight: 720,
        qualityPolicy: {
          tier: 'balanced',
          adaptiveQualityLevel: 0,
        },
      }),
    )
    expect(recordTiming).toHaveBeenCalledWith('audio', 1.2)
    expect(recordTiming).toHaveBeenCalledWith('spectrum', 2.3)
    expect(applyPreviewFrameReportMock).toHaveBeenCalledWith(
      expect.objectContaining({
        timestamp: 2400,
        spectrumBarCount: 96,
        qualityTier: 'balanced',
        adaptiveQualityLevel: 0,
        performanceScene: 'heavy-bloom',
        useWebGpuSpectrum: true,
        showDomPreviewBackground: true,
        showDomPreviewLogo: true,
        hasPostFx: true,
        gpuTiming: {
          instancesMs: 3.1,
          particlesMs: 4.2,
          renderMs: 5.3,
        },
        telemetry: {
          recordTiming,
          recordFrame,
          reportFrame,
        },
      }),
    )
  })


  it('skips playback reporting when the cadence helper says not to report', () => {
    applyPreviewPlaybackReportMock.mockReturnValue({
      didReport: false,
      nextReportedAt: 2200,
    })

    const reportPlaybackState = vi.fn()

    runPreviewFrame({
      frame: {
        timestamp: 2250,
        previousTimestamp: 2234,
      },
      scene: {
        viewport: {
          bounds: { width: 640, height: 360 },
          scale: 1,
          backgroundSrc: null,
          logoSrc: null,
          showFallbackScene: true,
          showDomPreviewBackground: false,
          showDomPreviewLogo: false,
          webgpuReady: false,
        },
        gpuNode: {
          atmosphereEnabled: false,
          submitFallbackScene: true,
          submitSpectrumInstances: false,
        },
        runtimeNode: {
          positionDraft: {
            anchor: 'center',
            positionX: 0,
            positionY: 0,
          },
          reactiveDraft: {} as never,
          gpuDrafts: {} as never,
          presentationDraft: {} as never,
        },
        transport: {
          currentPlaybackTimeSec: 0,
          selectedMp3Path: '',
          playback: { isReady: false },
        },
        capability: {
          label: 'Fallback',
          message: 'Fallback',
        },
        quality: {
          capabilityProfile: {
            rendererCapability: 'webgpu',
          },
          policy: {
            tier: 'compatibility',
            adaptiveQualityLevel: 0,
          },
        },
        performance: {
          primaryScene: 'baseline',
        },
        backgroundNode: {
          src: null,
          loadStatus: 'idle',
          domStyle: {},
        },
        logoNode: {
          enabled: false,
          src: null,
          loadStatus: 'idle',
          visibleRadiusRatio: 0,
          domStyle: {},
        },
        spectrumNode: {
          enabled: false,
          style: 'straight-bars',
          layers: [],
          attachment: null,
          barCount: 32,
          flyingGlowWingRelease: 0.8,
        },
        particlesNode: {
          enabled: false,
        },
        textNodes: {
          active: [],
          enabledCount: 0,
        },
        statusBadges: [],
      } as never,
      audioRuntimeRef: {
        current: {
          audioElement: { paused: true },
        },
      } as never,
      lastPlaybackReportAtRef: { current: 2200 },
      previewMotionRef: { current: {} } as never,
      particleStateRef: { current: {} } as never,
      telemetry: {
        recordTiming: vi.fn(),
        recordFrame: vi.fn(),
        reportFrame: vi.fn(),
      },
      reportPlaybackState,
      resolveAnchorPoint: vi.fn().mockReturnValue({ x: 320, y: 180 }),
      averageValues: vi.fn().mockReturnValue(0),
      buildLayerSpectrumValues: vi.fn().mockReturnValue([]),
      buildSyntheticSpectrumValues: vi.fn().mockReturnValue([]),
      smoothPreviewReactiveValue: vi.fn(),
      updateFlyingGlowWingEnvelope: vi.fn(),
      backdropCanvasRef: { current: null },
      backgroundImageRef: { current: null },
      domBackgroundImageRef: { current: null },
      domLogoLayerRef: { current: null },
      drawBackgroundLayer: vi.fn(),
      drawLogoLayer: vi.fn(),
      drawTextOverlays: vi.fn(),
      logoImageRef: { current: null },
      overlayCanvasRef: { current: null },
      applyDomBackgroundPresentation: vi.fn(),
      applyDomLogoPresentation: vi.fn(),
      webgpuRendererRef: { current: null },
    })

    expect(applyPreviewPlaybackReportMock).toHaveBeenCalledWith(
      expect.objectContaining({
        timestamp: 2250,
        lastReportedAt: 2200,
      }),
    )
  })
})
