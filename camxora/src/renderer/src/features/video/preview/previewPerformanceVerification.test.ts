import { evaluatePreviewPerformanceVerification } from '@/features/video/preview/previewPerformanceVerification'

describe('evaluatePreviewPerformanceVerification', () => {
  const compatibilityPolicy = {
    tier: 'compatibility',
    adaptiveQualityLevel: 0,
    maxDpr: 1.25,
    maxRenderPixels: 1600000,
    maxSpectrumBars: 84,
    maxParticleCount: 240,
    bloomEnabled: true,
    bloomQuality: 'full',
    allowMotionBlur: false,
    motionBlurQuality: 'off',
    targetFrameRate: 60,
  } as const

  const performancePolicy = {
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

  it('marks a compatibility-tier report as meeting the 60 FPS target when frame budgets are healthy', () => {
    const result = evaluatePreviewPerformanceVerification(
      {
        frames: 60,
        avgFrameMs: 15.9,
        maxFrameMs: 21,
        layoutAvgMs: 1,
        audioAvgMs: 1,
        spectrumAvgMs: 1.8,
        instancesAvgMs: 1.6,
        particlesAvgMs: 2.4,
        canvas2dAvgMs: 1,
        renderAvgMs: 6.8,
        dpr: 1.25,
        width: 1280,
        height: 720,
        barCount: 84,
        layerCount: 2,
        qualityTier: 'compatibility',
        adaptiveQualityLevel: 0,
        performanceScene: 'baseline',
        instanceCount: 120,
        particleCount: 80,
        useWebGpuSpectrum: true,
        showDomPreviewBackground: true,
        showDomPreviewLogo: true,
        postFx: true,
      },
      compatibilityPolicy,
    )

    expect(result.status).toBe('meeting-target')
    expect(result.targetFrameRate).toBe(60)
    expect(result.summary).toContain('60 FPS compatibility target')
  })

  it('marks a performance-tier report as near target when 120 FPS headroom is tight', () => {
    const result = evaluatePreviewPerformanceVerification(
      {
        frames: 120,
        avgFrameMs: 8.45,
        maxFrameMs: 12.4,
        layoutAvgMs: 0.8,
        audioAvgMs: 0.7,
        spectrumAvgMs: 1.2,
        instancesAvgMs: 1.4,
        particlesAvgMs: 2.1,
        canvas2dAvgMs: 0.9,
        renderAvgMs: 5.7,
        dpr: 2,
        width: 1920,
        height: 1080,
        barCount: 180,
        layerCount: 4,
        qualityTier: 'performance',
        adaptiveQualityLevel: 1,
        performanceScene: 'heavy-bloom',
        instanceCount: 420,
        particleCount: 520,
        useWebGpuSpectrum: true,
        showDomPreviewBackground: true,
        showDomPreviewLogo: true,
        postFx: true,
      },
      performancePolicy,
    )

    expect(result.status).toBe('near-target')
    expect(result.targetFrameRate).toBe(120)
    expect(result.usedAdaptiveFallback).toBe(true)
    expect(result.summary).toContain('with adaptive fallback active')
  })

  it('marks a high-particle scene as missing the target when frame pressure remains above budget', () => {
    const result = evaluatePreviewPerformanceVerification(
      {
        frames: 120,
        avgFrameMs: 11.6,
        maxFrameMs: 18.8,
        layoutAvgMs: 0.8,
        audioAvgMs: 0.7,
        spectrumAvgMs: 1.1,
        instancesAvgMs: 1.8,
        particlesAvgMs: 4.4,
        canvas2dAvgMs: 0.9,
        renderAvgMs: 7.2,
        dpr: 1.76,
        width: 1920,
        height: 1080,
        barCount: 154,
        layerCount: 3,
        qualityTier: 'performance',
        adaptiveQualityLevel: 2,
        performanceScene: 'high-particles',
        instanceCount: 360,
        particleCount: 499,
        useWebGpuSpectrum: true,
        showDomPreviewBackground: false,
        showDomPreviewLogo: true,
        postFx: true,
      },
      performancePolicy,
    )

    expect(result.status).toBe('missing-target')
    expect(result.targetFrameRate).toBe(120)
    expect(result.summary).toContain('high-particles stress scene')
  })

  it('keeps the base policy target when adaptive fallback has already reduced the live report tier metadata', () => {
    const result = evaluatePreviewPerformanceVerification(
      {
        frames: 120,
        avgFrameMs: 8.2,
        maxFrameMs: 12.1,
        layoutAvgMs: 0.8,
        audioAvgMs: 0.7,
        spectrumAvgMs: 1.1,
        instancesAvgMs: 1.2,
        particlesAvgMs: 1.9,
        canvas2dAvgMs: 0.9,
        renderAvgMs: 5.5,
        dpr: 1.76,
        width: 1920,
        height: 1080,
        barCount: 132,
        layerCount: 3,
        qualityTier: 'balanced',
        adaptiveQualityLevel: 1,
        performanceScene: 'max-layers',
        instanceCount: 260,
        particleCount: 360,
        useWebGpuSpectrum: true,
        showDomPreviewBackground: true,
        showDomPreviewLogo: true,
        postFx: true,
      },
      performancePolicy,
    )

    expect(result.targetFrameRate).toBe(120)
    expect(result.qualityTier).toBe('balanced')
    expect(result.usedAdaptiveFallback).toBe(true)
    expect(result.summary).toContain('120 FPS high-tier target')
  })
})
