import { runPreviewGpuRuntimeCoordinator } from '@/features/video/preview/previewGpuRuntimeCoordinator'

const mockPreparePreviewGpuDomains = vi.fn()
const mockOrchestratePreviewGpuSubmission = vi.fn()

vi.mock('@/features/video/preview/previewGpuDomainPreparation', () => ({
  preparePreviewGpuDomains: (...args: unknown[]) => mockPreparePreviewGpuDomains(...args),
}))

vi.mock('@/features/video/preview/previewGpuSubmissionOrchestrator', () => ({
  orchestratePreviewGpuSubmission: (...args: unknown[]) => mockOrchestratePreviewGpuSubmission(...args),
}))

describe('runPreviewGpuRuntimeCoordinator', () => {
  beforeEach(() => {
    mockPreparePreviewGpuDomains.mockReset()
    mockOrchestratePreviewGpuSubmission.mockReset()
  })

  it('composes domain preparation and shared submission orchestration', () => {
    const webgpuRenderer = {
      render: vi.fn(),
    }

    mockPreparePreviewGpuDomains.mockReturnValue({
      audioSignal: { reactiveEnergy: 0.7 },
      gradientAtlas: { width: 256, height: 2, rgba: new Uint8Array(256 * 2 * 4) },
      gpuInstances: [{ id: 'instance-a' }, { id: 'instance-b' }],
      gpuParticles: [{ id: 'particle-a' }],
      gpuParticleSimulation: { reactiveEnv: 0.5 },
      atmosphere: { haze: 0.2 },
      postFxPlan: {
        enabled: true,
        qualityTier: 'balanced',
      },
      postFx: { bloom: 0.4 },
      hasPostFx: true,
      timing: {
        instancesMs: 3.2,
        particlesMs: 4.6,
      },
    })
    mockOrchestratePreviewGpuSubmission.mockReturnValue({
      gpuInstances: [{ id: 'instance-a' }, { id: 'instance-b' }],
      gpuParticles: [{ id: 'particle-a' }],
      gpuParticleSimulation: { reactiveEnv: 0.5 },
      hasPostFx: true,
      timing: {
        instancesMs: 3.2,
        particlesMs: 4.6,
        renderMs: 6.7,
      },
    })

    const result = runPreviewGpuRuntimeCoordinator({
      analysedFrame: { styleMotionDrive: 0.45 } as never,
      audioSignal: {
        reactiveEnergy: 0.7,
        renderValues: [0.2, 0.4, 0.6],
      } as never,
      backdropSource: { kind: 'backdrop' } as never,
      buildLayerSpectrumValues: vi.fn(),
      buildSyntheticSpectrumValues: vi.fn(),
      centerX: 320,
      centerY: 180,
      deltaSec: 0.016,
      dpr: 1.5,
      gpuNode: {
        atmosphereEnabled: true,
        submitFallbackScene: false,
        submitSpectrumInstances: true,
      },
      hasBoundAudio: false,
      logicalHeight: 360,
      logicalWidth: 640,
      motionState: {
        flyingGlowPulseDrive: 0.9,
      },
      overlaySource: { kind: 'overlay' } as never,
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
      spectrumBarCount: 3,
      spectrumLayers: [
        { styleKey: 'flying-glow', mirrored: true, radiusOffset: 20 },
        { styleKey: 'straight-bars', mirrored: false, radiusOffset: 40 },
      ] as never,
      drafts: {
        atmosphere: {
          smokeEnabled: true,
        },
        particles: {
          particlesEnabled: true,
        },
        postFx: {
          particlesEnabled: true,
        },
        spectrum: {
          audioInputGain: 1.1,
          audioMotionSmoothing: 0.7,
          spectrumEnabled: true,
        },
      } as never,
      timeSec: 2,
      webgpuRenderer: webgpuRenderer as never,
    })

    expect(mockPreparePreviewGpuDomains).toHaveBeenCalledWith({
      atmosphereEnabled: true,
      atmosphereDraft: {
        smokeEnabled: true,
      },
      particles: {
        audioSignal: {
          reactiveEnergy: 0.7,
          renderValues: [0.2, 0.4, 0.6],
        },
        centerX: 320,
        centerY: 180,
        deltaSec: 0.016,
        logicalHeight: 360,
        logicalWidth: 640,
        particleState: { seed: 1 },
        qualityPolicy: {
          tier: 'balanced',
        },
        reactiveEnergy: 0.7,
        runtime: {
          envelope: { kick: 0.5, drop: 0.25 },
        },
        scale: 2,
        spectrumAttachment: {
          attachedToLogo: true,
          baseRadius: 100,
          centerOffsetX: 0,
          centerOffsetY: 0,
        },
        templateDraft: {
          particlesEnabled: true,
        },
      },
      postFxDraft: {
        particlesEnabled: true,
      },
      qualityPolicy: {
        tier: 'balanced',
      },
      reactiveEnergy: 0.7,
      spectrum: {
        analysedFrame: { styleMotionDrive: 0.45 },
        audioSignal: {
          reactiveEnergy: 0.7,
          renderValues: [0.2, 0.4, 0.6],
        },
        buildLayerSpectrumValues: expect.any(Function),
        buildSyntheticSpectrumValues: expect.any(Function),
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
          { styleKey: 'straight-bars', mirrored: false, radiusOffset: 40 },
        ],
        templateDraft: {
          audioInputGain: 1.1,
          audioMotionSmoothing: 0.7,
          spectrumEnabled: true,
        },
        timeSec: 2,
        useWebGpuSpectrum: true,
      },
    })
    expect(mockOrchestratePreviewGpuSubmission).toHaveBeenCalledWith({
      backdropSource: { kind: 'backdrop' },
      dpr: 1.5,
      domainResult: {
        audioSignal: { reactiveEnergy: 0.7 },
        gradientAtlas: { width: 256, height: 2, rgba: expect.any(Uint8Array) },
        gpuInstances: [{ id: 'instance-a' }, { id: 'instance-b' }],
        gpuParticles: [{ id: 'particle-a' }],
        gpuParticleSimulation: { reactiveEnv: 0.5 },
        atmosphere: { haze: 0.2 },
        postFxPlan: {
          enabled: true,
          qualityTier: 'balanced',
        },
        postFx: { bloom: 0.4 },
        hasPostFx: true,
        timing: {
          instancesMs: 3.2,
          particlesMs: 4.6,
        },
      },
      gpuNode: {
        atmosphereEnabled: true,
        submitFallbackScene: false,
        submitSpectrumInstances: true,
      },
      logicalHeight: 360,
      logicalWidth: 640,
      overlaySource: { kind: 'overlay' },
      webgpuRenderer,
    })
    expect(result.gpuInstances).toEqual([{ id: 'instance-a' }, { id: 'instance-b' }])
    expect(result.gpuParticles).toEqual([{ id: 'particle-a' }])
    expect(result.hasPostFx).toBe(true)
    expect(result.timing.renderMs).toBe(6.7)
  })
})
