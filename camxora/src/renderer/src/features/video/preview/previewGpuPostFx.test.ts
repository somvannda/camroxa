import {
  buildPreviewGpuPostFxPlan,
  mapPreviewGpuPostFxPlanToWebGpuSettings,
} from '@/features/video/preview/previewGpuPostFx'

const mockBuildPreviewGpuBloomPass = vi.fn()
const mockComputeSpectrumBloomStats = vi.fn()

vi.mock('@/features/video/preview/previewGpuBloomTuning', () => ({
  buildPreviewGpuBloomPass: (...args: unknown[]) => mockBuildPreviewGpuBloomPass(...args),
  computeSpectrumBloomStats: (...args: unknown[]) => mockComputeSpectrumBloomStats(...args),
}))

describe('previewGpuPostFx', () => {
  beforeEach(() => {
    mockBuildPreviewGpuBloomPass.mockReset()
    mockComputeSpectrumBloomStats.mockReset()
  })

  it('builds a shared post-fx plan from bloom stats, policy, and reactive energy', () => {
    mockComputeSpectrumBloomStats.mockReturnValue({ peak: 0.8 })
    mockBuildPreviewGpuBloomPass.mockReturnValue({
      enabled: true,
      threshold: 0.6,
      knee: 0.3,
      intensity: 1.1,
      bloomStrength: 0.4,
      blurScale: 1.2,
    })

    const result = buildPreviewGpuPostFxPlan({
      qualityPolicy: {
        tier: 'balanced',
        bloomEnabled: true,
        allowMotionBlur: false,
      } as never,
      reactiveEnergy: 0.7,
      spectrumLayers: [{ styleKey: 'straight-bars' }] as never,
      templateDraft: { particlesEnabled: true, spectrumEnabled: true, style: 'straight-bars' } as never,
    })

    expect(mockComputeSpectrumBloomStats).toHaveBeenCalledWith(
      expect.arrayContaining([expect.objectContaining({ styleKey: 'straight-bars' })]),
    )
    expect(mockBuildPreviewGpuBloomPass).toHaveBeenCalledWith(
      expect.objectContaining({ particlesEnabled: true, style: 'straight-bars' }),
      { peak: 0.8 },
      0.7,
    )
    expect(result).toEqual({
      enabled: true,
      qualityTier: 'balanced',
      bloom: expect.objectContaining({ bloomStrength: 0.4 }),
      motionBlur: expect.objectContaining({ enabled: false }),
      colorGrade: expect.objectContaining({ enabled: false }),
      composite: expect.objectContaining({ enabled: true, blendMode: 'screen' }),
    })
    expect(mapPreviewGpuPostFxPlanToWebGpuSettings(result)).toEqual({
      enabled: true,
      threshold: 0.6,
      knee: 0.3,
      intensity: 1.1,
      bloomStrength: 0.4,
      blurScale: 1.2,
      motionBlurStrength: 0,
      motionBlurShutterAngle: 0,
      motionBlurSamples: 0,
    })
  })

  it('skips shared post-fx entirely for flying glow so the wing stays sharp', () => {
    mockComputeSpectrumBloomStats.mockReturnValue({ peak: 0.8 })
    mockBuildPreviewGpuBloomPass.mockReturnValue({
      enabled: true,
      threshold: 0.55,
      knee: 0.28,
      intensity: 1.2,
      bloomStrength: 0.52,
      blurScale: 1.35,
    })

    const result = buildPreviewGpuPostFxPlan({
      qualityPolicy: {
        tier: 'performance',
        bloomEnabled: true,
        allowMotionBlur: true,
      } as never,
      reactiveEnergy: 0.8,
      spectrumLayers: [{ styleKey: 'flying-glow' }] as never,
      templateDraft: { particlesEnabled: true, spectrumEnabled: true, style: 'flying-glow' } as never,
    })

    expect(mockBuildPreviewGpuBloomPass).not.toHaveBeenCalled()
    expect(result).toBeNull()
    expect(mapPreviewGpuPostFxPlanToWebGpuSettings(result)).toBeNull()
  })

  it('returns null when policy disables bloom and no other pass is enabled', () => {
    mockComputeSpectrumBloomStats.mockReturnValue({ peak: 0 })

    const result = buildPreviewGpuPostFxPlan({
      qualityPolicy: {
        tier: 'compatibility',
        bloomEnabled: false,
        allowMotionBlur: false,
      } as never,
      reactiveEnergy: 0.1,
      spectrumLayers: [] as never,
      templateDraft: { particlesEnabled: false, spectrumEnabled: false, style: 'straight-bars' } as never,
    })

    expect(result).toBeNull()
    expect(mapPreviewGpuPostFxPlanToWebGpuSettings(result)).toBeNull()
  })

  it('uses the reduced temporal-history path when motion blur stays enabled outside the top tier', () => {
    mockComputeSpectrumBloomStats.mockReturnValue({ peak: 0.74 })
    mockBuildPreviewGpuBloomPass.mockReturnValue({
      enabled: true,
      threshold: 0.58,
      knee: 0.24,
      intensity: 1.06,
      bloomStrength: 0.33,
      blurScale: 1.08,
    })

    const result = buildPreviewGpuPostFxPlan({
      qualityPolicy: {
        tier: 'balanced',
        bloomEnabled: true,
        allowMotionBlur: true,
      } as never,
      reactiveEnergy: 0.45,
      spectrumLayers: [{ styleKey: 'wave-ribbon' }] as never,
      templateDraft: { particlesEnabled: false, spectrumEnabled: true, style: 'wave-ribbon' } as never,
    })

    expect(result).toEqual(
      expect.objectContaining({
        composite: expect.objectContaining({ blendMode: 'additive' }),
        motionBlur: expect.objectContaining({
          enabled: true,
          mode: 'temporal-history',
          sampleCount: 6,
          shutterAngle: 210,
        }),
      }),
    )
    expect(mapPreviewGpuPostFxPlanToWebGpuSettings(result)).toEqual(
      expect.objectContaining({
        motionBlurSamples: 6,
        motionBlurShutterAngle: 210,
      }),
    )
  })

  it('still enables temporal motion blur for non-flying-glow styles on performance tier', () => {
    mockComputeSpectrumBloomStats.mockReturnValue({ peak: 0.8 })
    mockBuildPreviewGpuBloomPass.mockReturnValue({
      enabled: true,
      threshold: 0.55,
      knee: 0.28,
      intensity: 1.2,
      bloomStrength: 0.52,
      blurScale: 1.35,
    })

    const result = buildPreviewGpuPostFxPlan({
      qualityPolicy: {
        tier: 'performance',
        bloomEnabled: true,
        allowMotionBlur: true,
      } as never,
      reactiveEnergy: 0.8,
      spectrumLayers: [{ styleKey: 'wave-ribbon' }] as never,
      templateDraft: { particlesEnabled: true, spectrumEnabled: true, style: 'wave-ribbon' } as never,
    })

    expect(result?.motionBlur).toEqual(
      expect.objectContaining({
        enabled: true,
        mode: 'temporal-history',
        sampleCount: 10,
        shutterAngle: 210,
      }),
    )
  })
})
