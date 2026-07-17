import { renderHook } from '@testing-library/react'

import { usePreviewProviderState } from '@/features/video/preview/usePreviewProviderState'

const usePreviewAssetServiceMock = vi.fn()
const usePreviewSurfaceLifecycleMock = vi.fn()
const usePreviewTransportCoordinatorMock = vi.fn()
const usePreviewSceneStateMock = vi.fn()
const usePreviewRuntimeMock = vi.fn()

vi.mock('@/features/video/preview/usePreviewAssetService', () => ({
  usePreviewAssetService: (...args: unknown[]) => usePreviewAssetServiceMock(...args),
}))

vi.mock('@/features/video/preview/usePreviewSurfaceLifecycle', () => ({
  usePreviewSurfaceLifecycle: (...args: unknown[]) => usePreviewSurfaceLifecycleMock(...args),
}))

vi.mock('@/features/video/preview/usePreviewTransportCoordinator', () => ({
  usePreviewTransportCoordinator: (...args: unknown[]) =>
    usePreviewTransportCoordinatorMock(...args),
}))

vi.mock('@/features/video/preview/usePreviewSceneState', () => ({
  usePreviewSceneState: (...args: unknown[]) => usePreviewSceneStateMock(...args),
}))

vi.mock('@/features/video/preview/usePreviewRuntime', () => ({
  usePreviewRuntime: (...args: unknown[]) => usePreviewRuntimeMock(...args),
}))

describe('usePreviewProviderState', () => {
  beforeEach(() => {
    usePreviewAssetServiceMock.mockReset()
    usePreviewSurfaceLifecycleMock.mockReset()
    usePreviewTransportCoordinatorMock.mockReset()
    usePreviewSceneStateMock.mockReset()
    usePreviewRuntimeMock.mockReset()
  })

  it('composes provider state from the extracted asset, surface, transport, scene, and runtime hooks', () => {
    const containerRef = { current: document.createElement('div') }
    const webgpuCanvasRef = { current: document.createElement('canvas') }
    const backgroundImageRef = { current: null }
    const logoImageRef = { current: null }
    const domBackgroundImageRef = { current: null }
    const domLogoLayerRef = { current: null }
    const backdropCanvasRef = { current: null }
    const overlayCanvasRef = { current: null }
    const webgpuRendererRef = { current: null }
    const audioRuntimeRef = { current: {} }
    const lastPlaybackReportAtRef = { current: 0 }
    const onTelemetryReport = vi.fn()
    const performanceVerification = {
      status: 'near-target',
      summary: 'Preview is near the 60 FPS compatibility target on the heavy-bloom stress scene.',
      targetFrameRate: 60,
      frameBudgetMs: 16.67,
      qualityTier: 'balanced',
      adaptiveQualityLevel: 1,
      performanceScene: 'heavy-bloom',
      usedAdaptiveFallback: true,
      avgFrameMs: 17.1,
      maxFrameMs: 24,
      renderAvgMs: 11,
      particlesAvgMs: 3.8,
    }
    const scene = {
      capability: { label: 'WebGPU', message: 'Ready' },
      viewport: { showFallbackScene: false },
      runtimeNode: {},
      textNodes: {},
      spectrumNode: {},
      backgroundNode: {},
      logoNode: {},
      transport: {},
      particlesNode: {},
      statusBadges: [],
    }

    usePreviewAssetServiceMock.mockReturnValue({
      backgroundImageRef,
      backgroundLoadStatus: 'ready',
      backgroundSrc: 'blob:bg',
      capability: 'webgpu',
      logoImageRef,
      logoLoadStatus: 'ready',
      logoSrc: 'blob:logo',
      logoVisibleRadiusRatio: 0.7,
    })
    usePreviewSurfaceLifecycleMock.mockReturnValue({
      backdropCanvasRef,
      bounds: { width: 1280, height: 720 },
      capabilityProfile: {
        rendererCapability: 'webgpu',
      },
      containerRef,
      onTelemetryReport,
      overlayCanvasRef,
      performanceVerification,
      qualityPolicy: {
        tier: 'balanced',
        adaptiveQualityLevel: 0,
        maxDpr: 1.5,
        maxRenderPixels: 2200000,
        maxSpectrumBars: 140,
        maxParticleCount: 480,
        bloomEnabled: true,
        bloomQuality: 'full',
        allowMotionBlur: false,
        motionBlurQuality: 'off',
        targetFrameRate: 60,
      },
      webgpuErrorMessage: null,
      webgpuCanvasRef,
      webgpuRendererRef,
      webgpuStatus: 'ready',
    })
    usePreviewTransportCoordinatorMock.mockReturnValue({
      audioRuntimeRef,
      lastPlaybackReportAtRef,
      reportPlaybackState: vi.fn(),
    })
    usePreviewSceneStateMock.mockReturnValue(scene)

    const options = {
      backgroundPath: 'D:/background.png',
      buildDomBackgroundStyle: vi.fn(),
      buildDomLogoStyle: vi.fn(),
      buildLayerSpectrumValues: vi.fn(),
      buildSyntheticSpectrumValues: vi.fn(),
      drawBackgroundLayer: vi.fn(),
      drawLogoLayer: vi.fn(),
      drawTextOverlays: vi.fn(),
      logoPath: 'D:/logo.png',
      onPlaybackStateChange: vi.fn(),
      playbackCommand: null,
      previewVolume: 0.8,
      resolveAnchorPoint: vi.fn(),
      resolveSpectrumBarCount: vi.fn(),
      resolveTextOverlayState: vi.fn(),
      selectedMp3Path: 'D:/track.mp3',
      selectedTextOverlayIndex: 0,
      smoothPreviewReactiveValue: vi.fn(),
      template: { id: 'template-1' },
      templateDraft: {
        logoEnabled: true,
        logoShape: 'circle',
        audioMotionSmoothing: 0.6,
      },
      updateFlyingGlowWingEnvelope: vi.fn(),
      averageValues: vi.fn(),
      applyDomBackgroundPresentation: vi.fn(),
      applyDomLogoPresentation: vi.fn(),
      workspace: {
        previewAspectRatio: 16 / 9,
        playback: { isReady: true },
      },
    } as never

    const { result } = renderHook(() => usePreviewProviderState(options))

    expect(usePreviewAssetServiceMock).toHaveBeenCalledWith({
      backgroundPath: 'D:/background.png',
      logoEnabled: true,
      logoPath: 'D:/logo.png',
      logoShape: 'circle',
    })
    expect(usePreviewSurfaceLifecycleMock).toHaveBeenCalledWith({
      capability: 'webgpu',
    })
    expect(usePreviewTransportCoordinatorMock).toHaveBeenCalledWith(
      expect.objectContaining({
        audioMotionSmoothing: 0.6,
        previewVolume: 0.8,
        selectedMp3Path: 'D:/track.mp3',
      }),
    )
    expect(usePreviewSceneStateMock).toHaveBeenCalledWith(
      expect.objectContaining({
        backgroundImageRef,
        capability: 'webgpu',
        logoSrc: 'blob:logo',
        template: { id: 'template-1' },
      }),
    )
    expect(usePreviewRuntimeMock).toHaveBeenCalledWith(
      expect.objectContaining({
        scene,
        webgpuCanvasRef,
        domBackgroundImageRef,
        domLogoLayerRef,
        onTelemetryReport,
      }),
    )
    expect(result.current).toEqual({
      containerRef,
      domBackgroundImageRef,
      domLogoLayerRef,
      lifecycleState: {
        canRecover: false,
        capability: 'webgpu',
        fallbackActive: false,
        label: 'Preview Running',
        lastError: null,
        message: 'Renderer preview is live through the WebGPU compositor.',
        status: 'running',
        webgpuStatus: 'ready',
      },
      manualRenderFrame: null,
      playbackReady: true,
      performanceVerification,
      scene,
      webgpuCanvasRef,
      webgpuRendererRef,
    })
  })
})
