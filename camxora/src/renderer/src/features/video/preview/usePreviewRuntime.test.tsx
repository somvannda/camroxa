import { renderHook } from '@testing-library/react'

import { usePreviewRuntime } from '@/features/video/preview/usePreviewRuntime'

const startPreviewAnimationLoopMock = vi.fn()
const createPreviewRuntimeDiagnosticsMock = vi.fn()
const runPreviewFrameMock = vi.fn()

vi.mock('@/features/video/preview/previewAnimationLoop', () => ({
  startPreviewAnimationLoop: (...args: unknown[]) => startPreviewAnimationLoopMock(...args),
}))

vi.mock('@/features/video/preview/previewRuntimeDiagnostics', () => ({
  createPreviewRuntimeDiagnostics: (...args: unknown[]) =>
    createPreviewRuntimeDiagnosticsMock(...args),
}))

vi.mock('@/features/video/preview/previewFrameRunner', () => ({
  runPreviewFrame: (...args: unknown[]) => runPreviewFrameMock(...args),
}))

describe('usePreviewRuntime', () => {
  beforeEach(() => {
    startPreviewAnimationLoopMock.mockReset()
    createPreviewRuntimeDiagnosticsMock.mockReset()
    runPreviewFrameMock.mockReset()
  })

  it('wires diagnostics, starts the animation loop, and delegates frames to the runner', () => {
    vi.spyOn(navigator, 'userAgent', 'get').mockReturnValue('Mozilla/5.0')

    const stop = vi.fn()
    const telemetry = { recordTiming: vi.fn(), recordFrame: vi.fn(), reportFrame: vi.fn() }
    const scene = { capability: { label: 'x', message: 'y' } }
    const onTelemetryReport = vi.fn()
    createPreviewRuntimeDiagnosticsMock.mockReturnValue({ telemetry })
    startPreviewAnimationLoopMock.mockImplementation(({ onFrame }) => {
      onFrame({ previousTimestamp: 1000, timestamp: 1016 })
      return stop
    })

    const options = {
      audioRuntimeRef: { current: {} },
      backdropCanvasRef: { current: null },
      backgroundImageRef: { current: null },
      buildLayerSpectrumValues: vi.fn(),
      buildSyntheticSpectrumValues: vi.fn(),
      domBackgroundImageRef: { current: null },
      domLogoLayerRef: { current: null },
      drawBackgroundLayer: vi.fn(),
      drawLogoLayer: vi.fn(),
      drawTextOverlays: vi.fn(),
      logoImageRef: { current: null },
      overlayCanvasRef: { current: null },
      particleStateRef: { current: {} },
      previewMotionRef: { current: {} },
      reportPlaybackState: vi.fn(),
      resolveAnchorPoint: vi.fn(),
      scene,
      smoothPreviewReactiveValue: vi.fn(),
      updateFlyingGlowWingEnvelope: vi.fn(),
      webgpuCanvasRef: { current: document.createElement('canvas') },
      webgpuRendererRef: { current: null },
      averageValues: vi.fn(),
      applyDomBackgroundPresentation: vi.fn(),
      applyDomLogoPresentation: vi.fn(),
      onTelemetryReport,
      lastPlaybackReportAtRef: { current: 0 },
    } as never

    const { unmount } = renderHook(() => usePreviewRuntime(options))

    expect(createPreviewRuntimeDiagnosticsMock).toHaveBeenCalledWith({
      onReport: onTelemetryReport,
    })
    expect(startPreviewAnimationLoopMock).toHaveBeenCalledWith(
      expect.objectContaining({
        initialTimestamp: expect.any(Number),
        onFrame: expect.any(Function),
      }),
    )
    expect(runPreviewFrameMock).toHaveBeenCalledWith(
      expect.objectContaining({
        frame: { previousTimestamp: 1000, timestamp: 1016 },
        telemetry,
        scene,
      }),
    )

    unmount()
    expect(stop).toHaveBeenCalledTimes(1)
  })
})
