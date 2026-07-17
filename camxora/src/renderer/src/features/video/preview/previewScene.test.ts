import { buildVideoTemplateDraft } from '@/features/video/core/contracts/videoTemplateDraft'
import { buildVideoPreviewScene } from '@/features/video/preview/previewScene'

describe('buildVideoPreviewScene', () => {
  it('builds a scene payload with viewport, node, and badge state', () => {
    const draft = buildVideoTemplateDraft(
      {
        style: 'flying-glow',
        previewBindings: { spectrumAttachToLogo: true, spectrumLogoGap: 32 },
        logoSettings: { enabled: true, circleMask: true, size: 220 },
        particles: { enabled: true },
      },
      { logoPath: 'D:/logo.png' },
    )

    const scene = buildVideoPreviewScene({
      bounds: { width: 1280, height: 720 },
      currentPlaybackTimeSec: 12.4,
      draft,
      backgroundSrc: 'blob:background',
      backgroundLoadStatus: 'ready',
      capabilityProfile: {
        rendererCapability: 'webgpu',
      } as never,
      domBackgroundStyle: { opacity: 0.8 },
      domLogoStyle: { opacity: 1 },
      logoLoadStatus: 'ready',
      logoSrc: 'blob:logo',
      logoVisibleRadiusRatio: 0.76,
      scale: 1,
      selectedMp3Path: 'D:/song.mp3',
      playback: { isReady: true },
      spectrumAttachment: {
        attachedToLogo: true,
        baseRadius: 144,
        centerOffsetX: 0,
        centerOffsetY: 0,
      },
      spectrumBarCount: 112,
      spectrumLayers: [{ styleKey: 'flying-glow', mirrored: true, radiusOffset: 20 }] as never,
      activeTextOverlays: [{ key: 'title' }],
      enabledTextOverlayCount: 1,
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
      } as never,
      capability: 'webgpu',
      webgpuStatus: 'ready',
    })

    expect(scene.viewport.showDomPreviewBackground).toBe(true)
    expect(scene.viewport.showDomPreviewLogo).toBe(true)
    expect(scene.gpuNode.submitFallbackScene).toBe(false)
    expect(scene.gpuNode.submitSpectrumInstances).toBe(true)
    expect(scene.runtimeNode.positionDraft.anchor).toBe(draft.anchor)
    expect(scene.runtimeNode.gpuDrafts.spectrum.spectrumEnabled).toBe(true)
    expect(scene.capability.label).toBe('WebGPU Compositor Live')
    expect(scene.quality.policy.tier).toBe('balanced')
    expect(scene.performance.primaryScene).toBe('heavy-bloom')
    expect(scene.performance.activeScenes).toEqual(['heavy-bloom'])
    expect(scene.spectrumNode.barCount).toBe(112)
    expect(scene.logoNode.visibleRadiusRatio).toBe(0.76)
    expect(scene.textNodes.active).toEqual([{ key: 'title' }])
    expect(scene.statusBadges).toEqual(['Compositor surface active', 'GPU particles active'])
  })

  it('falls back cleanly when assets are missing or compositor is unavailable', () => {
    const draft = buildVideoTemplateDraft(
      {
        style: 'straight-bars',
        logoSettings: { enabled: false, circleMask: false, size: 180 },
      },
      { logoPath: '' },
    )

    const scene = buildVideoPreviewScene({
      bounds: { width: 960, height: 540 },
      currentPlaybackTimeSec: 0,
      draft,
      backgroundSrc: null,
      backgroundLoadStatus: 'idle',
      capabilityProfile: {
        rendererCapability: 'css',
      } as never,
      domBackgroundStyle: {},
      domLogoStyle: {},
      logoLoadStatus: 'idle',
      logoSrc: null,
      logoVisibleRadiusRatio: 1,
      scale: 1,
      selectedMp3Path: '',
      playback: { isReady: false },
      spectrumAttachment: null,
      spectrumBarCount: 140,
      spectrumLayers: [],
      activeTextOverlays: [],
      enabledTextOverlayCount: 0,
      qualityPolicy: {
        tier: 'compatibility',
        adaptiveQualityLevel: 0,
        maxDpr: 1,
        maxRenderPixels: 1250000,
        maxSpectrumBars: 72,
        maxParticleCount: 160,
        bloomEnabled: false,
        bloomQuality: 'off',
        allowMotionBlur: false,
        motionBlurQuality: 'off',
        targetFrameRate: 60,
      } as never,
      capability: 'css',
      webgpuStatus: 'error',
    })

    expect(scene.viewport.showFallbackScene).toBe(true)
    expect(scene.gpuNode.submitFallbackScene).toBe(true)
    expect(scene.gpuNode.submitSpectrumInstances).toBe(false)
    expect(scene.runtimeNode.presentationDraft.logoEnabled).toBe(false)
    expect(scene.capability.message).toContain('does not currently expose WebGPU')
    expect(scene.performance.primaryScene).toBe('baseline')
    expect(scene.statusBadges).toEqual(['GPU particles active'])
  })

  it('keeps the background fully disabled when the background toggle is off', () => {
    const draft = buildVideoTemplateDraft(
      {
        backgroundSettings: {
          enabled: false,
        },
      },
      { logoPath: '' },
    )

    const scene = buildVideoPreviewScene({
      bounds: { width: 960, height: 540 },
      currentPlaybackTimeSec: 0,
      draft,
      backgroundSrc: 'blob:background',
      backgroundLoadStatus: 'ready',
      capabilityProfile: {
        rendererCapability: 'webgpu',
      } as never,
      domBackgroundStyle: {},
      domLogoStyle: {},
      logoLoadStatus: 'idle',
      logoSrc: null,
      logoVisibleRadiusRatio: 1,
      scale: 1,
      selectedMp3Path: '',
      playback: { isReady: false },
      spectrumAttachment: null,
      spectrumBarCount: 140,
      spectrumLayers: [],
      activeTextOverlays: [],
      enabledTextOverlayCount: 0,
      qualityPolicy: {
        tier: 'compatibility',
        adaptiveQualityLevel: 0,
        maxDpr: 1,
        maxRenderPixels: 1250000,
        maxSpectrumBars: 72,
        maxParticleCount: 160,
        bloomEnabled: false,
        bloomQuality: 'off',
        allowMotionBlur: false,
        motionBlurQuality: 'off',
        targetFrameRate: 60,
      } as never,
      capability: 'webgpu',
      webgpuStatus: 'ready',
    })

    expect(scene.backgroundNode.enabled).toBe(false)
    expect(scene.backgroundNode.src).toBeNull()
    expect(scene.backgroundNode.loadStatus).toBe('idle')
    expect(scene.viewport.showDomPreviewBackground).toBe(false)
    expect(scene.viewport.showFallbackScene).toBe(false)
    expect(scene.gpuNode.submitFallbackScene).toBe(false)
  })
})
