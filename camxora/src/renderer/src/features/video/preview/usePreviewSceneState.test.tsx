import { renderHook } from '@testing-library/react'

import { usePreviewSceneState } from '@/features/video/preview/usePreviewSceneState'

const mockBuildSpectrumLayers = vi.fn()
const mockResolveSpectrumAttachment = vi.fn()
const mockBuildVideoPreviewScene = vi.fn()

vi.mock('@/features/video/domains/spectrum/spectrumLayerModel', () => ({
  buildSpectrumLayers: (...args: unknown[]) => mockBuildSpectrumLayers(...args),
}))

vi.mock('@/features/video/core/scene/attachmentService', () => ({
  resolveSpectrumAttachment: (...args: unknown[]) => mockResolveSpectrumAttachment(...args),
}))

vi.mock('@/features/video/preview/previewScene', () => ({
  buildVideoPreviewScene: (...args: unknown[]) => mockBuildVideoPreviewScene(...args),
}))

describe('usePreviewSceneState', () => {
  beforeEach(() => {
    mockBuildSpectrumLayers.mockReset()
    mockResolveSpectrumAttachment.mockReset()
    mockBuildVideoPreviewScene.mockReset()
  })

  it('composes preview scene inputs for provider consumption', () => {
    const spectrumLayers = [{ id: 'layer-a' }]
    const spectrumAttachment = { attachedToLogo: true }
    const rawTemplateLayers = [{ id: 'raw-layer' }]
    const scene = {
      capability: { label: 'ok', message: 'ok' },
      spectrumNode: {
        style: 'straight-bars',
        layers: spectrumLayers,
        barCount: 96,
      },
    }

    mockBuildSpectrumLayers.mockReturnValue(spectrumLayers)
    mockResolveSpectrumAttachment.mockReturnValue(spectrumAttachment)
    mockBuildVideoPreviewScene.mockReturnValue(scene)

    const buildDomBackgroundStyle = vi.fn().mockReturnValue({ opacity: 0.7 })
    const buildDomLogoStyle = vi.fn().mockReturnValue({ opacity: 1 })
    const resolveSpectrumBarCount = vi.fn().mockReturnValue(96)
    const resolveTextOverlayState = vi.fn().mockReturnValue({
      activeTextOverlays: [{ key: 'title' }],
      enabledTextOverlayCount: 1,
    })

    const { result } = renderHook(() =>
      usePreviewSceneState({
        backgroundImageRef: { current: null },
        backgroundLoadStatus: 'ready',
        backgroundSrc: 'blob:bg',
        bounds: { width: 1280, height: 720 },
        buildDomBackgroundStyle,
        buildDomLogoStyle,
        capability: 'webgpu',
        capabilityProfile: {
          rendererCapability: 'webgpu',
        } as never,
        logoLoadStatus: 'ready',
        logoSrc: 'blob:logo',
        logoVisibleRadiusRatio: 0.78,
        qualityPolicy: {
          tier: 'balanced',
          maxSpectrumBars: 140,
        } as never,
        resolveSpectrumBarCount,
        resolveTextOverlayState,
        selectedMp3Path: 'D:/song.mp3',
        selectedTextOverlayIndex: 0,
        template: { layers: rawTemplateLayers },
        templateDraft: {
          logoEnabled: true,
          particlesEnabled: false,
          spectrumEnabled: true,
          style: 'straight-bars',
          flyingGlowWingRelease: 1,
          textOverlays: [],
        } as never,
        webgpuStatus: 'ready',
        workspace: {
          playback: {
            currentTimeSec: 12,
            isReady: true,
          },
          previewAspectRatio: {
            width: 1920,
            height: 1080,
          },
        } as never,
      }),
    )

    expect(resolveTextOverlayState).toHaveBeenCalledWith(
      expect.objectContaining({
        currentPlaybackTimeSec: 12,
        selectedTextOverlayIndex: 0,
      }),
    )
    expect(mockBuildSpectrumLayers).toHaveBeenCalledWith(
      expect.objectContaining({
        layers: rawTemplateLayers,
        style: 'straight-bars',
      }),
    )
    expect(resolveSpectrumBarCount).toHaveBeenCalledWith(
      expect.objectContaining({
        bounds: { width: 1280, height: 720 },
        spectrumAttachment,
        spectrumLayers,
      }),
    )
    expect(mockBuildVideoPreviewScene).toHaveBeenCalledWith(
      expect.objectContaining({
        activeTextOverlays: [{ key: 'title' }],
        backgroundSrc: 'blob:bg',
        capability: 'webgpu',
        capabilityProfile: {
          rendererCapability: 'webgpu',
        },
        qualityPolicy: {
          tier: 'balanced',
          maxSpectrumBars: 140,
        },
        spectrumAttachment,
        spectrumBarCount: 96,
        spectrumLayers,
      }),
    )
    expect(result.current).toBe(scene)
  })

  it('raises flying glow solid-band bar density before quality clamping', () => {
    const rawTemplateLayers = [{ id: 'raw-layer', styleKey: 'flying-glow', solidBand: true }]
    const scene = {
      capability: { label: 'ok', message: 'ok' },
      spectrumNode: {
        style: 'flying-glow',
        layers: [{ id: 'layer-a', solidBand: true }],
        barCount: 140,
      },
    }

    mockBuildSpectrumLayers.mockReturnValue([{ id: 'layer-a', solidBand: true }])
    mockResolveSpectrumAttachment.mockReturnValue(null)
    mockBuildVideoPreviewScene.mockReturnValue(scene)

    const resolveSpectrumBarCount = vi.fn().mockReturnValue(180)

    renderHook(() =>
      usePreviewSceneState({
        backgroundImageRef: { current: null },
        backgroundLoadStatus: 'ready',
        backgroundSrc: 'blob:bg',
        bounds: { width: 1280, height: 720 },
        buildDomBackgroundStyle: vi.fn().mockReturnValue({ opacity: 0.7 }),
        buildDomLogoStyle: vi.fn().mockReturnValue({ opacity: 1 }),
        capability: 'webgpu',
        capabilityProfile: {
          rendererCapability: 'webgpu',
        } as never,
        logoLoadStatus: 'ready',
        logoSrc: 'blob:logo',
        logoVisibleRadiusRatio: 0.78,
        qualityPolicy: {
          tier: 'balanced',
          maxSpectrumBars: 140,
        } as never,
        resolveSpectrumBarCount,
        resolveTextOverlayState: vi.fn().mockReturnValue({
          activeTextOverlays: [],
          enabledTextOverlayCount: 0,
        }),
        selectedMp3Path: 'D:/song.mp3',
        selectedTextOverlayIndex: 0,
        template: { layers: rawTemplateLayers },
        templateDraft: {
          logoEnabled: true,
          particlesEnabled: false,
          spectrumEnabled: true,
          style: 'flying-glow',
          flyingGlowWingRelease: 1,
          textOverlays: [],
        } as never,
        webgpuStatus: 'ready',
        workspace: {
          playback: {
            currentTimeSec: 12,
            isReady: true,
          },
          previewAspectRatio: {
            width: 1920,
            height: 1080,
          },
        } as never,
      }),
    )

    expect(resolveSpectrumBarCount).toHaveBeenCalled()
    expect(mockBuildVideoPreviewScene).toHaveBeenCalledWith(
      expect.objectContaining({
        spectrumBarCount: 140,
      }),
    )
  })

  it('normalizes ratio-only preview references before deriving scale', () => {
    mockBuildSpectrumLayers.mockReturnValue([])
    mockResolveSpectrumAttachment.mockReturnValue(null)
    mockBuildVideoPreviewScene.mockReturnValue({
      capability: { label: 'ok', message: 'ok' },
      spectrumNode: {
        style: 'straight-bars',
        layers: [],
        barCount: 64,
      },
    })

    const buildDomLogoStyle = vi.fn().mockReturnValue({ opacity: 1 })

    renderHook(() =>
      usePreviewSceneState({
        backgroundImageRef: { current: null },
        backgroundLoadStatus: 'idle',
        backgroundSrc: null,
        bounds: { width: 960, height: 540 },
        buildDomBackgroundStyle: vi.fn().mockReturnValue({}),
        buildDomLogoStyle,
        capability: 'webgpu',
        capabilityProfile: {
          rendererCapability: 'webgpu',
        } as never,
        logoLoadStatus: 'idle',
        logoSrc: null,
        logoVisibleRadiusRatio: 0.5,
        qualityPolicy: {
          tier: 'balanced',
          maxSpectrumBars: 140,
        } as never,
        resolveSpectrumBarCount: vi.fn().mockReturnValue(64),
        resolveTextOverlayState: vi.fn().mockReturnValue({
          activeTextOverlays: [],
          enabledTextOverlayCount: 0,
        }),
        selectedMp3Path: '',
        selectedTextOverlayIndex: 0,
        template: { layers: [] },
        templateDraft: {
          logoEnabled: false,
          particlesEnabled: true,
          spectrumEnabled: true,
          style: 'straight-bars',
          flyingGlowWingRelease: 1,
          textOverlays: [],
        } as never,
        webgpuStatus: 'idle',
        workspace: {
          playback: {
            currentTimeSec: 0,
            isReady: false,
          },
          previewAspectRatio: {
            width: 16,
            height: 9,
          },
        } as never,
      }),
    )

    expect(buildDomLogoStyle).toHaveBeenCalledWith(
      expect.objectContaining({
        scale: 0.5,
      }),
    )
    expect(mockBuildVideoPreviewScene).toHaveBeenCalledWith(
      expect.objectContaining({
        scale: 0.5,
      }),
    )
  })
})
