import { render, screen } from '@testing-library/react'

import { RendererVideoPreviewSurface } from '@/features/video/preview/RendererVideoPreviewSurface'

describe('RendererVideoPreviewSurface', () => {
  beforeEach(() => {
    vi.spyOn(window, 'requestAnimationFrame').mockImplementation((callback: FrameRequestCallback) => {
      callback(16)
      return 1
    })
    vi.spyOn(window, 'cancelAnimationFrame').mockImplementation(() => {})
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('keeps performance verification internal while the preview is healthy', () => {
    const onLifecycleStateChange = vi.fn()
    const lifecycleState = {
      status: 'running',
      message: 'Preview runtime healthy.',
      lastError: null,
      canRecover: false,
      capability: 'webgpu',
    }

    render(
      <RendererVideoPreviewSurface
        containerRef={{ current: null }}
        domBackgroundImageRef={{ current: null }}
        domLogoLayerRef={{ current: null }}
        lifecycleState={lifecycleState as never}
        onLifecycleStateChange={onLifecycleStateChange}
        performanceVerification={{
          status: 'meeting-target',
          summary: 'Preview is meeting the 120 FPS high-tier target on the heavy-bloom stress scene.',
          targetFrameRate: 120,
          frameBudgetMs: 8.33,
          qualityTier: 'performance',
          adaptiveQualityLevel: 0,
          performanceScene: 'heavy-bloom',
          usedAdaptiveFallback: false,
          avgFrameMs: 7.9,
          maxFrameMs: 10.2,
          renderAvgMs: 4.8,
          particlesAvgMs: 1.6,
        }}
        playbackReady
        scene={{
          capability: {
            label: 'WebGPU Compositor Live',
            message: 'Renderer is healthy.',
          },
          viewport: {
            showFallbackScene: false,
            showDomPreviewBackground: false,
            showDomPreviewLogo: false,
          },
          backgroundNode: {
            enabled: true,
            src: 'file:///background.png',
            loadStatus: 'ready',
            domStyle: {},
          },
          logoNode: {
            enabled: false,
            src: null,
            loadStatus: 'idle',
            domStyle: {},
          },
          statusBadges: [],
        } as never}
        webgpuCanvasRef={{ current: null }}
      />,
    )

    expect(screen.getByText('WebGPU Compositor Live')).toBeInTheDocument()
    expect(screen.queryByText(/120 FPS high-tier target/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/heavy-bloom stress scene/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/meeting-target/i)).not.toBeInTheDocument()
    expect(screen.queryByText('Preview runtime healthy.')).not.toBeInTheDocument()
    expect(onLifecycleStateChange).toHaveBeenCalledWith(lifecycleState)
  })

  it('enables direct preview-surface dragging without rendering a visible drag handle', () => {
    const containerRef = { current: null as HTMLDivElement | null }
    const onSpectrumPositionChange = vi.fn()

    render(
      <RendererVideoPreviewSurface
        containerRef={containerRef}
        domBackgroundImageRef={{ current: null }}
        domLogoLayerRef={{ current: null }}
        lifecycleState={{
          status: 'running',
          message: 'ok',
          lastError: null,
          canRecover: false,
          capability: 'webgpu',
        } as never}
        performanceVerification={null}
        playbackReady
        scene={{
          capability: { label: 'WebGPU Compositor Live', message: 'ok' },
          viewport: {
            bounds: { width: 400, height: 200 },
            scale: 2,
            showFallbackScene: false,
            showDomPreviewBackground: false,
            showDomPreviewLogo: false,
          },
          runtimeNode: {
            positionDraft: {
              anchor: 'center',
              positionX: 0,
              positionY: 0,
            },
          },
          backgroundNode: {
            enabled: true,
            src: null,
            loadStatus: 'idle',
            domStyle: {},
          },
          logoNode: {
            enabled: false,
            src: null,
            loadStatus: 'idle',
            domStyle: {},
          },
          spectrumNode: {
            enabled: true,
            attachment: null,
          },
          statusBadges: [],
        } as never}
        webgpuCanvasRef={{ current: null }}
        enableSpectrumPositionEditing
        onSpectrumPositionChange={onSpectrumPositionChange}
      />,
    )

    expect(screen.queryByTestId('renderer-spectrum-drag-handle')).not.toBeInTheDocument()
    expect(containerRef.current).not.toBeNull()
    expect(containerRef.current).toHaveClass('cursor-grab')
    expect(onSpectrumPositionChange).not.toHaveBeenCalled()
  })
})
