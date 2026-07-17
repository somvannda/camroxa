import { preparePreviewGpuDomains } from '@/features/video/preview/previewGpuDomainPreparation'

const mockBuildAtmosphereGpuSettings = vi.fn()
const mockBuildPreviewSpectrumGpuInstances = vi.fn()
const mockBuildPreviewParticleGpuState = vi.fn()
const mockBuildPreviewGpuPostFxPlan = vi.fn()
const mockMapPreviewGpuPostFxPlanToWebGpuSettings = vi.fn()

vi.mock('@/features/video/domains/atmosphere/atmosphereGpuRuntime', () => ({
  buildAtmosphereGpuSettings: (...args: unknown[]) => mockBuildAtmosphereGpuSettings(...args),
}))

vi.mock('@/features/video/domains/spectrum/spectrumGpuRuntime', () => ({
  buildSpectrumGpuInstances: (...args: unknown[]) => mockBuildPreviewSpectrumGpuInstances(...args),
}))

vi.mock('@/features/video/domains/particles/particleGpuRuntime', () => ({
  buildParticleGpuState: (...args: unknown[]) => mockBuildPreviewParticleGpuState(...args),
}))

vi.mock('@/features/video/preview/previewGpuPostFx', () => ({
  buildPreviewGpuPostFxPlan: (...args: unknown[]) => mockBuildPreviewGpuPostFxPlan(...args),
  mapPreviewGpuPostFxPlanToWebGpuSettings: (...args: unknown[]) =>
    mockMapPreviewGpuPostFxPlanToWebGpuSettings(...args),
}))

describe('preparePreviewGpuDomains', () => {
  beforeEach(() => {
    mockBuildAtmosphereGpuSettings.mockReset()
    mockBuildPreviewSpectrumGpuInstances.mockReset()
    mockBuildPreviewParticleGpuState.mockReset()
    mockBuildPreviewGpuPostFxPlan.mockReset()
    mockMapPreviewGpuPostFxPlanToWebGpuSettings.mockReset()
  })

  it('prepares spectrum, particles, and effects from scene-owned GPU policy', () => {
    mockBuildPreviewSpectrumGpuInstances.mockReturnValue({
      gradientAtlas: { width: 256, height: 1, rgba: new Uint8Array(256 * 4) },
      gpuInstances: [{ id: 'instance-a' }],
      instancesMs: 3.2,
    })
    mockBuildPreviewParticleGpuState.mockReturnValue({
      gpuParticles: [{ id: 'particle-a' }],
      gpuParticleSimulation: { reactiveEnv: 0.5 },
      particlesMs: 4.6,
    })
    mockBuildAtmosphereGpuSettings.mockReturnValue({ haze: 0.2 })
    mockBuildPreviewGpuPostFxPlan.mockReturnValue({
      enabled: true,
      qualityTier: 'balanced',
      bloom: { enabled: true, bloomStrength: 0.4 },
      motionBlur: { enabled: false },
      colorGrade: { enabled: false },
      composite: { enabled: true },
    })
    mockMapPreviewGpuPostFxPlanToWebGpuSettings.mockReturnValue({ bloom: 0.4 })

    const result = preparePreviewGpuDomains({
      atmosphereEnabled: true,
      atmosphereDraft: {
        smokeEnabled: true,
      } as never,
      particles: {
        audioSignal: {
          reactiveEnergy: 0.7,
          styleMotionDrive: 0.5,
          styleTriggerDrive: 0.65,
        } as never,
        centerX: 320,
        centerY: 180,
        deltaSec: 0.016,
        logicalHeight: 360,
        logicalWidth: 640,
        particleState: { seed: 1 } as never,
        qualityPolicy: {
          tier: 'balanced',
        } as never,
        reactiveEnergy: 0.7,
        runtime: {
          envelope: { kick: 0.5, drop: 0.25 },
        } as never,
        scale: 2,
        spectrumAttachment: {
          attachedToLogo: true,
          baseRadius: 100,
          centerOffsetX: 0,
          centerOffsetY: 0,
        },
        templateDraft: {
          particlesEnabled: true,
        } as never,
      },
      postFxDraft: {
        particlesEnabled: true,
        spectrumEnabled: true,
        style: 'flying-glow',
      } as never,
      qualityPolicy: {
        tier: 'balanced',
        bloomEnabled: true,
      } as never,
      reactiveEnergy: 0.7,
      spectrum: {
        analysedFrame: { styleMotionDrive: 0.45 } as never,
        audioSignal: {
          reactiveEnergy: 0.7,
          renderValues: [0.2, 0.4, 0.6],
        } as never,
        buildLayerSpectrumValues: vi.fn(),
        buildSyntheticSpectrumValues: vi.fn(),
        centerX: 320,
        centerY: 180,
        hasBoundAudio: false,
        motionState: {
          flyingGlowPulseDrive: 0.9,
        },
        reactiveEnergy: 0.7,
        scale: 2,
        spectrumAttachment: {
          attachedToLogo: true,
          baseRadius: 100,
          centerOffsetX: 0,
          centerOffsetY: 0,
        },
        spectrumBarCount: 3,
        spectrumLayers: [
          { styleKey: 'flying-glow', mirrored: true, radiusOffset: 20 },
        ] as never,
        templateDraft: {
          audioInputGain: 1.1,
          audioMotionSmoothing: 0.7,
          spectrumEnabled: true,
        } as never,
        timeSec: 2,
        useWebGpuSpectrum: true,
      },
    })

    expect(mockBuildPreviewSpectrumGpuInstances).toHaveBeenCalledWith(
      expect.objectContaining({
        centerX: 320,
        centerY: 180,
        useWebGpuSpectrum: true,
      }),
    )
    expect(mockBuildPreviewParticleGpuState).toHaveBeenCalledWith(
      expect.objectContaining({
        logicalWidth: 640,
        logicalHeight: 360,
        reactiveEnergy: 0.7,
        qualityPolicy: {
          tier: 'balanced',
        },
      }),
    )
    expect(mockBuildAtmosphereGpuSettings).toHaveBeenCalledWith({
      atmosphereEnabled: true,
      templateDraft: { smokeEnabled: true },
      timeSec: 2,
    })
    expect(mockBuildPreviewGpuPostFxPlan).toHaveBeenCalledWith({
      qualityPolicy: expect.objectContaining({ tier: 'balanced' }),
      reactiveEnergy: 0.7,
      spectrumLayers: [
        { styleKey: 'flying-glow', mirrored: true, radiusOffset: 20 },
      ],
      templateDraft: {
        particlesEnabled: true,
        spectrumEnabled: true,
        style: 'flying-glow',
      },
    })
    expect(mockMapPreviewGpuPostFxPlanToWebGpuSettings).toHaveBeenCalledWith(
      expect.objectContaining({
        enabled: true,
        qualityTier: 'balanced',
      }),
    )
    expect(result).toEqual({
      audioSignal: {
        reactiveEnergy: 0.7,
        renderValues: [0.2, 0.4, 0.6],
      },
      gradientAtlas: {
        width: 256,
        height: 1,
        rgba: expect.any(Uint8Array),
      },
      gpuInstances: [{ id: 'instance-a' }],
      gpuParticles: [{ id: 'particle-a' }],
      gpuParticleSimulation: { reactiveEnv: 0.5 },
      atmosphere: { haze: 0.2 },
      postFxPlan: expect.objectContaining({
        enabled: true,
        qualityTier: 'balanced',
      }),
      postFx: { bloom: 0.4 },
      hasPostFx: true,
      timing: {
        instancesMs: 3.2,
        particlesMs: 4.6,
      },
    })
  })
})
