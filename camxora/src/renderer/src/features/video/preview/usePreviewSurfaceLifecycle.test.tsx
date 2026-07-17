import type { JSX } from 'react'
import { act, render, screen, waitFor } from '@testing-library/react'

import { usePreviewSurfaceLifecycle } from '@/features/video/preview/usePreviewSurfaceLifecycle'

const mockDestroy = vi.fn()
const mockInitialize = vi.fn()

vi.mock('@/features/video/webgpu/webgpuSpectrumRenderer', () => ({
  WebGpuSpectrumRenderer: vi.fn().mockImplementation(() => ({
    destroy: mockDestroy,
    initialize: (...args: unknown[]) => mockInitialize(...args),
  })),
}))

describe('usePreviewSurfaceLifecycle', () => {
  beforeEach(() => {
    mockDestroy.mockReset()
    mockInitialize.mockReset()
    mockInitialize.mockResolvedValue({
      capabilityProfile: {
        rendererCapability: 'webgpu',
        webgpuAvailable: true,
        preferredCanvasFormat: 'bgra8unorm',
        isFallbackAdapter: false,
        maxBufferSize: 268435456,
        maxStorageBufferBindingSize: 134217728,
        maxTextureDimension2D: 8192,
        maxComputeInvocationsPerWorkgroup: 512,
        maxComputeWorkgroupSizeX: 256,
        maxComputeWorkgroupStorageSize: 32768,
        featureFlags: [],
      },
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
    })
  })

  it('marks non-webgpu capability as unsupported without starting the renderer', async () => {
    function Harness(): JSX.Element {
      const { containerRef, webgpuCanvasRef, webgpuStatus } = usePreviewSurfaceLifecycle({
        capability: 'css',
      })

      return (
        <div ref={containerRef}>
          <canvas ref={webgpuCanvasRef} />
          <span data-testid="status">{webgpuStatus}</span>
        </div>
      )
    }

    render(<Harness />)

    await waitFor(() => {
      expect(screen.getByTestId('status').textContent).toBe('unsupported')
    })

    expect(mockInitialize).not.toHaveBeenCalled()
  })

  it('moves the WebGPU surface into device-lost when the renderer reports device loss', async () => {
    let reportDeviceLost: ((message: string) => void) | null = null
    mockInitialize.mockImplementation((_canvas, options?: { onDeviceLost?: (message: string) => void }) => {
      reportDeviceLost = options?.onDeviceLost ?? null
      return Promise.resolve({
        capabilityProfile: {
          rendererCapability: 'webgpu',
          webgpuAvailable: true,
          preferredCanvasFormat: 'bgra8unorm',
          isFallbackAdapter: false,
          maxBufferSize: 268435456,
          maxStorageBufferBindingSize: 134217728,
          maxTextureDimension2D: 8192,
          maxComputeInvocationsPerWorkgroup: 512,
          maxComputeWorkgroupSizeX: 256,
          maxComputeWorkgroupStorageSize: 32768,
          featureFlags: [],
        },
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
      })
    })

    function Harness(): JSX.Element {
      const { containerRef, webgpuCanvasRef, webgpuStatus } = usePreviewSurfaceLifecycle({
        capability: 'webgpu',
      })

      return (
        <div ref={containerRef}>
          <canvas ref={webgpuCanvasRef} />
          <span data-testid="status">{webgpuStatus}</span>
        </div>
      )
    }

    render(<Harness />)

    await waitFor(() => {
      expect(screen.getByTestId('status').textContent).toBe('ready')
    })

    act(() => {
      reportDeviceLost?.('GPU lost')
    })

    await waitFor(() => {
      expect(screen.getByTestId('status').textContent).toBe('device-lost')
    })

    expect(mockDestroy).toHaveBeenCalled()
  })

  it('derives a reduced effective quality policy after repeated overloaded telemetry reports', async () => {
    let latestHook: ReturnType<typeof usePreviewSurfaceLifecycle> | null = null

    function Harness(): JSX.Element {
      latestHook = usePreviewSurfaceLifecycle({
        capability: 'webgpu',
      })

      return (
        <div ref={latestHook.containerRef}>
          <canvas ref={latestHook.webgpuCanvasRef} />
          <span data-testid="status">{latestHook.webgpuStatus}</span>
          <span data-testid="level">{String(latestHook.qualityPolicy.adaptiveQualityLevel)}</span>
          <span data-testid="particles">{String(latestHook.qualityPolicy.maxParticleCount)}</span>
          <span data-testid="performance-status">
            {latestHook.performanceVerification?.status ?? 'none'}
          </span>
          <span data-testid="performance-target">
            {String(latestHook.performanceVerification?.targetFrameRate ?? 0)}
          </span>
        </div>
      )
    }

    render(<Harness />)

    await waitFor(() => {
      expect(screen.getByTestId('status').textContent).toBe('ready')
    })

    act(() => {
      latestHook?.onTelemetryReport({
        frames: 30,
        avgFrameMs: 24,
        maxFrameMs: 40,
        layoutAvgMs: 1.2,
        audioAvgMs: 1.4,
        spectrumAvgMs: 0.9,
        instancesAvgMs: 2.8,
        particlesAvgMs: 6,
        canvas2dAvgMs: 1.1,
        renderAvgMs: 12,
        dpr: 1.5,
        width: 1280,
        height: 720,
        barCount: 140,
        layerCount: 3,
        qualityTier: 'balanced',
        adaptiveQualityLevel: 0,
        performanceScene: 'high-particles',
        instanceCount: 320,
        particleCount: 480,
        useWebGpuSpectrum: true,
        showDomPreviewBackground: true,
        showDomPreviewLogo: true,
        postFx: true,
      })
      latestHook?.onTelemetryReport({
        frames: 30,
        avgFrameMs: 23,
        maxFrameMs: 38,
        layoutAvgMs: 1.1,
        audioAvgMs: 1.3,
        spectrumAvgMs: 0.8,
        instancesAvgMs: 2.6,
        particlesAvgMs: 5.8,
        canvas2dAvgMs: 1,
        renderAvgMs: 11.5,
        dpr: 1.5,
        width: 1280,
        height: 720,
        barCount: 140,
        layerCount: 3,
        qualityTier: 'balanced',
        adaptiveQualityLevel: 0,
        performanceScene: 'high-particles',
        instanceCount: 320,
        particleCount: 480,
        useWebGpuSpectrum: true,
        showDomPreviewBackground: true,
        showDomPreviewLogo: true,
        postFx: true,
      })
    })

    await waitFor(() => {
      expect(screen.getByTestId('level').textContent).toBe('1')
    })

    expect(screen.getByTestId('particles').textContent).toBe('355')
    expect(screen.getByTestId('performance-status').textContent).toBe('missing-target')
    expect(screen.getByTestId('performance-target').textContent).toBe('60')
  })
})
