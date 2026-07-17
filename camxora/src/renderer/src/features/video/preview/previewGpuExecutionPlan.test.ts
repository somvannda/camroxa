import { buildPreviewGpuExecutionPlan } from '@/features/video/preview/previewGpuExecutionPlan'

describe('buildPreviewGpuExecutionPlan', () => {
  it('keeps spectrum instances in the plan when submission is enabled', () => {
    const plan = buildPreviewGpuExecutionPlan({
      audioSignal: { reactiveEnergy: 0.7 } as never,
      atmosphere: { haze: 0.2 } as never,
      backdropSource: { kind: 'backdrop' } as never,
      dpr: 1.5,
      logicalHeight: 360,
      logicalWidth: 640,
      overlaySource: { kind: 'overlay' } as never,
      particles: [{ id: 'particle-a' }] as never,
      particleSimulation: { reactiveEnv: 0.5 } as never,
      postFx: { bloom: 0.4 } as never,
      spectrumGradientAtlas: { width: 256, height: 1, rgba: new Uint8Array(256 * 4) } as never,
      submitFallbackScene: false,
      submitSpectrumInstances: true,
      spectrumInstances: [{ id: 'instance-a' }] as never,
    })

    expect(plan).toEqual({
      audioSignal: { reactiveEnergy: 0.7 },
      atmosphere: { haze: 0.2 },
      backdropSource: { kind: 'backdrop' },
      dpr: 1.5,
      fallbackScene: false,
      gradientAtlas: { width: 256, height: 1, rgba: expect.any(Uint8Array) },
      height: 360,
      instances: [{ id: 'instance-a' }],
      overlaySource: { kind: 'overlay' },
      particles: [{ id: 'particle-a' }],
      particleSimulation: { reactiveEnv: 0.5 },
      postFx: { bloom: 0.4 },
      width: 640,
    })
  })

  it('drops spectrum instances from the plan when submission is disabled', () => {
    const plan = buildPreviewGpuExecutionPlan({
      audioSignal: null,
      atmosphere: null,
      backdropSource: null,
      dpr: 1,
      logicalHeight: 720,
      logicalWidth: 1280,
      overlaySource: null,
      particles: [],
      particleSimulation: null,
      postFx: null,
      spectrumGradientAtlas: { width: 256, height: 1, rgba: new Uint8Array(256 * 4) } as never,
      submitFallbackScene: true,
      submitSpectrumInstances: false,
      spectrumInstances: [{ id: 'instance-a' }] as never,
    })

    expect(plan.instances).toEqual([])
    expect(plan.gradientAtlas).toBeNull()
    expect(plan.fallbackScene).toBe(true)
    expect(plan.width).toBe(1280)
    expect(plan.height).toBe(720)
  })
})
