import { resolvePreviewPerformanceNode } from '@/features/video/preview/previewPerformanceScenes'

describe('resolvePreviewPerformanceNode', () => {
  const basePolicy = {
    tier: 'performance',
    adaptiveQualityLevel: 0,
    maxDpr: 2,
    maxRenderPixels: 3600000,
    maxSpectrumBars: 180,
    maxParticleCount: 960,
    bloomEnabled: true,
    bloomQuality: 'full',
    allowMotionBlur: true,
    motionBlurQuality: 'full',
    targetFrameRate: 120,
  } as const

  const baseDraft = {
    style: 'straight-bars',
    spectrumEnabled: true,
    particlesEnabled: false,
    particlesMaxCount: 180,
    smokeEnabled: false,
    vignetteEnabled: false,
  } as const

  it('returns a baseline scene when no dominant stressor is active', () => {
    const result = resolvePreviewPerformanceNode({
      draft: baseDraft as never,
      enabledTextOverlayCount: 1,
      qualityPolicy: basePolicy,
      spectrumBarCount: 72,
      spectrumLayers: [{ glow: 14, blur: 2 }] as never,
    })

    expect(result.primaryScene).toBe('baseline')
    expect(result.activeScenes).toEqual([])
  })

  it('classifies max-layer scenes from dense spectrum layering and atmosphere pressure', () => {
    const result = resolvePreviewPerformanceNode({
      draft: {
        ...baseDraft,
        smokeEnabled: true,
      } as never,
      enabledTextOverlayCount: 1,
      qualityPolicy: basePolicy,
      spectrumBarCount: 148,
      spectrumLayers: [
        { glow: 16, blur: 2 },
        { glow: 18, blur: 3 },
        { glow: 14, blur: 2 },
        { glow: 12, blur: 1 },
      ] as never,
    })

    expect(result.primaryScene).toBe('max-layers')
    expect(result.activeScenes).toContain('max-layers')
  })

  it('classifies luminous scenes as heavy bloom', () => {
    const result = resolvePreviewPerformanceNode({
      draft: {
        ...baseDraft,
        style: 'halo-stack',
      } as never,
      enabledTextOverlayCount: 1,
      qualityPolicy: basePolicy,
      spectrumBarCount: 120,
      spectrumLayers: [{ glow: 76, blur: 18 }] as never,
    })

    expect(result.primaryScene).toBe('heavy-bloom')
    expect(result.activeScenes).toContain('heavy-bloom')
    expect(result.maxGlow).toBe(76)
  })

  it('classifies scenes with large particle budgets as high-particles', () => {
    const result = resolvePreviewPerformanceNode({
      draft: {
        ...baseDraft,
        particlesEnabled: true,
        particlesMaxCount: 840,
      } as never,
      enabledTextOverlayCount: 1,
      qualityPolicy: basePolicy,
      spectrumBarCount: 96,
      spectrumLayers: [{ glow: 18, blur: 2 }] as never,
    })

    expect(result.primaryScene).toBe('high-particles')
    expect(result.activeScenes).toContain('high-particles')
    expect(result.particleBudget).toBe(840)
  })

  it('classifies scenes with many active overlays as text-overlay-pressure', () => {
    const result = resolvePreviewPerformanceNode({
      draft: baseDraft as never,
      enabledTextOverlayCount: 4,
      qualityPolicy: basePolicy,
      spectrumBarCount: 96,
      spectrumLayers: [{ glow: 18, blur: 2 }] as never,
    })

    expect(result.primaryScene).toBe('text-overlay-pressure')
    expect(result.activeScenes).toContain('text-overlay-pressure')
    expect(result.textOverlayCount).toBe(4)
  })

  it('respects the effective quality-policy cap before classifying a scene as high-particles', () => {
    const result = resolvePreviewPerformanceNode({
      draft: {
        ...baseDraft,
        particlesEnabled: true,
        particlesMaxCount: 840,
      } as never,
      enabledTextOverlayCount: 1,
      qualityPolicy: {
        ...basePolicy,
        adaptiveQualityLevel: 2,
        maxParticleCount: 320,
      },
      spectrumBarCount: 96,
      spectrumLayers: [{ glow: 18, blur: 2 }] as never,
    })

    expect(result.particleBudget).toBe(320)
    expect(result.activeScenes).not.toContain('high-particles')
    expect(result.primaryScene).toBe('baseline')
  })
})
