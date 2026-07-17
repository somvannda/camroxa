import {
  advancePreviewAdaptiveQualityState,
  createPreviewAdaptiveQualityState,
  resolveAdaptivePreviewQualityPolicy,
} from '@/features/video/preview/previewAdaptiveQuality'

describe('previewAdaptiveQuality', () => {
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

  it('derives reduced and minimal fallback policies from one base policy seam', () => {
    const reduced = resolveAdaptivePreviewQualityPolicy(basePolicy, 1)
    const minimal = resolveAdaptivePreviewQualityPolicy(basePolicy, 2)

    expect(reduced.adaptiveQualityLevel).toBe(1)
    expect(reduced.maxParticleCount).toBeLessThan(basePolicy.maxParticleCount)
    expect(reduced.bloomQuality).toBe('reduced')
    expect(reduced.motionBlurQuality).toBe('reduced')

    expect(minimal.adaptiveQualityLevel).toBe(2)
    expect(minimal.bloomEnabled).toBe(false)
    expect(minimal.allowMotionBlur).toBe(false)
    expect(minimal.maxSpectrumBars).toBeLessThan(reduced.maxSpectrumBars)
  })

  it('degrades after repeated overloaded telemetry samples and recovers with sustained headroom', () => {
    let state = createPreviewAdaptiveQualityState()

    state = advancePreviewAdaptiveQualityState(
      state,
      {
        frames: 60,
        avgFrameMs: 14,
        maxFrameMs: 22,
        layoutAvgMs: 1,
        audioAvgMs: 1,
        spectrumAvgMs: 2,
        instancesAvgMs: 1,
        particlesAvgMs: 5,
        canvas2dAvgMs: 1,
        renderAvgMs: 9,
        dpr: 1.5,
        width: 1280,
        height: 720,
        barCount: 140,
        layerCount: 2,
        qualityTier: 'performance',
        adaptiveQualityLevel: 0,
        performanceScene: 'high-particles',
        instanceCount: 300,
        particleCount: 600,
        useWebGpuSpectrum: true,
        showDomPreviewBackground: true,
        showDomPreviewLogo: true,
        postFx: true,
      },
      basePolicy,
    )
    expect(state.level).toBe(0)

    state = advancePreviewAdaptiveQualityState(
      state,
      {
        frames: 60,
        avgFrameMs: 15,
        maxFrameMs: 23,
        layoutAvgMs: 1,
        audioAvgMs: 1,
        spectrumAvgMs: 2,
        instancesAvgMs: 1,
        particlesAvgMs: 5,
        canvas2dAvgMs: 1,
        renderAvgMs: 9,
        dpr: 1.5,
        width: 1280,
        height: 720,
        barCount: 140,
        layerCount: 2,
        qualityTier: 'performance',
        adaptiveQualityLevel: 0,
        performanceScene: 'high-particles',
        instanceCount: 300,
        particleCount: 600,
        useWebGpuSpectrum: true,
        showDomPreviewBackground: true,
        showDomPreviewLogo: true,
        postFx: true,
      },
      basePolicy,
    )
    expect(state.level).toBe(1)

    state = advancePreviewAdaptiveQualityState(
      state,
      {
        frames: 60,
        avgFrameMs: 6,
        maxFrameMs: 8,
        layoutAvgMs: 1,
        audioAvgMs: 1,
        spectrumAvgMs: 1,
        instancesAvgMs: 1,
        particlesAvgMs: 1,
        canvas2dAvgMs: 1,
        renderAvgMs: 2,
        dpr: 1.25,
        width: 1280,
        height: 720,
        barCount: 120,
        layerCount: 2,
        qualityTier: 'performance',
        adaptiveQualityLevel: 1,
        performanceScene: 'heavy-bloom',
        instanceCount: 240,
        particleCount: 420,
        useWebGpuSpectrum: true,
        showDomPreviewBackground: true,
        showDomPreviewLogo: true,
        postFx: true,
      },
      basePolicy,
    )
    state = advancePreviewAdaptiveQualityState(
      state,
      {
        frames: 60,
        avgFrameMs: 6,
        maxFrameMs: 8,
        layoutAvgMs: 1,
        audioAvgMs: 1,
        spectrumAvgMs: 1,
        instancesAvgMs: 1,
        particlesAvgMs: 1,
        canvas2dAvgMs: 1,
        renderAvgMs: 2,
        dpr: 1.25,
        width: 1280,
        height: 720,
        barCount: 120,
        layerCount: 2,
        qualityTier: 'performance',
        adaptiveQualityLevel: 1,
        performanceScene: 'heavy-bloom',
        instanceCount: 240,
        particleCount: 420,
        useWebGpuSpectrum: true,
        showDomPreviewBackground: true,
        showDomPreviewLogo: true,
        postFx: true,
      },
      basePolicy,
    )
    state = advancePreviewAdaptiveQualityState(
      state,
      {
        frames: 60,
        avgFrameMs: 6,
        maxFrameMs: 8,
        layoutAvgMs: 1,
        audioAvgMs: 1,
        spectrumAvgMs: 1,
        instancesAvgMs: 1,
        particlesAvgMs: 1,
        canvas2dAvgMs: 1,
        renderAvgMs: 2,
        dpr: 1.25,
        width: 1280,
        height: 720,
        barCount: 120,
        layerCount: 2,
        qualityTier: 'performance',
        adaptiveQualityLevel: 1,
        performanceScene: 'heavy-bloom',
        instanceCount: 240,
        particleCount: 420,
        useWebGpuSpectrum: true,
        showDomPreviewBackground: true,
        showDomPreviewLogo: true,
        postFx: true,
      },
      basePolicy,
    )

    expect(state.level).toBe(0)
  })

  it('escalates to the minimal fallback level when overload persists after one reduction', () => {
    let state = createPreviewAdaptiveQualityState()

    state = advancePreviewAdaptiveQualityState(
      state,
      {
        frames: 60,
        avgFrameMs: 15,
        maxFrameMs: 24,
        layoutAvgMs: 1,
        audioAvgMs: 1,
        spectrumAvgMs: 2,
        instancesAvgMs: 1.4,
        particlesAvgMs: 5.1,
        canvas2dAvgMs: 1,
        renderAvgMs: 9.1,
        dpr: 1.5,
        width: 1280,
        height: 720,
        barCount: 140,
        layerCount: 2,
        qualityTier: 'performance',
        adaptiveQualityLevel: 0,
        performanceScene: 'heavy-bloom',
        instanceCount: 320,
        particleCount: 640,
        useWebGpuSpectrum: true,
        showDomPreviewBackground: true,
        showDomPreviewLogo: true,
        postFx: true,
      },
      basePolicy,
    )
    state = advancePreviewAdaptiveQualityState(
      state,
      {
        frames: 60,
        avgFrameMs: 16,
        maxFrameMs: 24.5,
        layoutAvgMs: 1,
        audioAvgMs: 1,
        spectrumAvgMs: 2,
        instancesAvgMs: 1.5,
        particlesAvgMs: 5.4,
        canvas2dAvgMs: 1,
        renderAvgMs: 9.3,
        dpr: 1.5,
        width: 1280,
        height: 720,
        barCount: 140,
        layerCount: 2,
        qualityTier: 'performance',
        adaptiveQualityLevel: 0,
        performanceScene: 'heavy-bloom',
        instanceCount: 320,
        particleCount: 640,
        useWebGpuSpectrum: true,
        showDomPreviewBackground: true,
        showDomPreviewLogo: true,
        postFx: true,
      },
      basePolicy,
    )

    expect(state.level).toBe(1)

    state = advancePreviewAdaptiveQualityState(
      state,
      {
        frames: 60,
        avgFrameMs: 17.1,
        maxFrameMs: 27,
        layoutAvgMs: 1,
        audioAvgMs: 1,
        spectrumAvgMs: 2,
        instancesAvgMs: 1.5,
        particlesAvgMs: 5.8,
        canvas2dAvgMs: 1,
        renderAvgMs: 9.8,
        dpr: 1.25,
        width: 1280,
        height: 720,
        barCount: 128,
        layerCount: 2,
        qualityTier: 'performance',
        adaptiveQualityLevel: 1,
        performanceScene: 'high-particles',
        instanceCount: 280,
        particleCount: 500,
        useWebGpuSpectrum: true,
        showDomPreviewBackground: true,
        showDomPreviewLogo: true,
        postFx: true,
      },
      basePolicy,
    )
    state = advancePreviewAdaptiveQualityState(
      state,
      {
        frames: 60,
        avgFrameMs: 17.4,
        maxFrameMs: 27.5,
        layoutAvgMs: 1,
        audioAvgMs: 1,
        spectrumAvgMs: 2,
        instancesAvgMs: 1.6,
        particlesAvgMs: 5.9,
        canvas2dAvgMs: 1,
        renderAvgMs: 9.9,
        dpr: 1.25,
        width: 1280,
        height: 720,
        barCount: 128,
        layerCount: 2,
        qualityTier: 'performance',
        adaptiveQualityLevel: 1,
        performanceScene: 'high-particles',
        instanceCount: 280,
        particleCount: 500,
        useWebGpuSpectrum: true,
        showDomPreviewBackground: true,
        showDomPreviewLogo: true,
        postFx: true,
      },
      basePolicy,
    )

    expect(state.level).toBe(2)
    expect(resolveAdaptivePreviewQualityPolicy(basePolicy, state.level)).toEqual(
      expect.objectContaining({
        adaptiveQualityLevel: 2,
        bloomEnabled: false,
        allowMotionBlur: false,
      }),
    )
  })
})
