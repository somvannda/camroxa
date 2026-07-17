import { buildParticleGpuState } from '@/features/video/domains/particles/particleGpuRuntime'

const mockUpdateParticleSimulation = vi.fn()

vi.mock('@/features/video/domains/particles/particleSimulation', () => ({
  updateParticleSimulation: (...args: unknown[]) => mockUpdateParticleSimulation(...args),
}))

describe('buildParticleGpuState', () => {
  beforeEach(() => {
    mockUpdateParticleSimulation.mockReset()
  })

  it('delegates particle simulation through the particle domain runtime seam', () => {
    mockUpdateParticleSimulation.mockReturnValue([{ id: 'particle-a' }])

    const result = buildParticleGpuState({
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
        maxParticleCount: 480,
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
    })

    expect(mockUpdateParticleSimulation).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({ particlesEnabled: true }),
      320,
      180,
      640,
      360,
      100,
      2,
      0.016,
      0.7,
      { reactiveEnergy: 0.7, styleMotionDrive: 0.5, styleTriggerDrive: 0.65 },
      { kick: 0.5, drop: 0.25 },
    )
    expect(result.gpuParticles).toEqual([{ id: 'particle-a' }])
    expect(result.gpuParticleSimulation).toEqual(
      expect.objectContaining({
        centerX: 320,
        centerY: 180,
        opacity: expect.any(Number),
      }),
    )
    expect(result.particlesMs).toEqual(expect.any(Number))
  })

  it('uses the minimum anchor radius when no spectrum attachment radius is available', () => {
    mockUpdateParticleSimulation.mockReturnValue([])

    buildParticleGpuState({
      audioSignal: null,
      centerX: 0,
      centerY: 0,
      deltaSec: 0.02,
      logicalHeight: 200,
      logicalWidth: 100,
      particleState: {} as never,
      qualityPolicy: {
        tier: 'compatibility',
        maxParticleCount: 240,
      } as never,
      reactiveEnergy: 0.1,
      runtime: {
        envelope: { kick: 0, drop: 0 },
      } as never,
      scale: 1.5,
      spectrumAttachment: null,
      templateDraft: {
        particlesEnabled: false,
      } as never,
    })

    expect(mockUpdateParticleSimulation).toHaveBeenCalledWith(
      expect.anything(),
      expect.anything(),
      0,
      0,
      100,
      200,
      27,
      1.5,
      0.02,
      0.1,
      null,
      { kick: 0, drop: 0 },
    )
  })

  it('caps particle count through the shared quality policy before delegating simulation', () => {
    mockUpdateParticleSimulation.mockReturnValue([{ id: 'particle-capped' }])

    const particleState = {
      reactiveEnv: 0.46,
      triggerEnv: 0.72,
      timeSec: 4.2,
    }

    const result = buildParticleGpuState({
      audioSignal: {
        reactiveEnergy: 0.5,
        styleMotionDrive: 0.44,
        styleTriggerDrive: 0.7,
      } as never,
      centerX: 120,
      centerY: 96,
      deltaSec: 0.016,
      logicalHeight: 360,
      logicalWidth: 640,
      particleState: particleState as never,
      qualityPolicy: {
        tier: 'compatibility',
        maxParticleCount: 240,
      } as never,
      reactiveEnergy: 0.5,
      runtime: {
        envelope: { kick: 0.18, drop: 0.64 },
      } as never,
      scale: 1.25,
      spectrumAttachment: null,
      templateDraft: {
        particlesEnabled: true,
        particlesMaxCount: 1200,
        particlesDrift: 0.5,
        particlesSwirl: 0.75,
        particlesReactivity: 0.8,
        particlesOpacity: 0.65,
        particlesColor: '#204060',
        particlesReactColor: '#ff8040',
        particlesReactStrength: 0.9,
      } as never,
    })

    expect(mockUpdateParticleSimulation).toHaveBeenCalledWith(
      particleState,
      expect.objectContaining({
        particlesEnabled: true,
        particlesMaxCount: 240,
      }),
      120,
      96,
      640,
      360,
      22.5,
      1.25,
      0.016,
      0.5,
      { reactiveEnergy: 0.5, styleMotionDrive: 0.44, styleTriggerDrive: 0.7 },
      { kick: 0.18, drop: 0.64 },
    )
    expect(result.gpuParticles).toEqual([{ id: 'particle-capped' }])
    expect(result.gpuParticleSimulation).toEqual(
      expect.objectContaining({
        timeSec: 4.2,
        reactiveEnv: 0.46,
        triggerEnv: 0.72,
        opacity: 0.65,
      }),
    )
    expect((result.gpuParticleSimulation?.red ?? 0) > 0.4).toBe(true)
  })

  it('keeps an enabled particle layer from collapsing to an empty max count', () => {
    mockUpdateParticleSimulation.mockReturnValue([{ id: 'particle-floor' }])

    buildParticleGpuState({
      audioSignal: null,
      centerX: 0,
      centerY: 0,
      deltaSec: 0.016,
      logicalHeight: 360,
      logicalWidth: 640,
      particleState: {} as never,
      qualityPolicy: {
        tier: 'compatibility',
        maxParticleCount: 240,
      } as never,
      reactiveEnergy: 0.1,
      runtime: {
        envelope: { kick: 0, drop: 0 },
      } as never,
      scale: 1,
      spectrumAttachment: null,
      templateDraft: {
        particlesEnabled: true,
        particlesMaxCount: 0,
      } as never,
    })

    expect(mockUpdateParticleSimulation).toHaveBeenCalled()
    expect(mockUpdateParticleSimulation.mock.calls[0]?.[1]).toEqual(
      expect.objectContaining({
        particlesEnabled: true,
        particlesMaxCount: 1,
      }),
    )
  })

  it('applies professional motion baselines even when drift and swirl sliders are zero', () => {
    mockUpdateParticleSimulation.mockReturnValue([{ id: 'particle-style-baseline' }])

    const result = buildParticleGpuState({
      audioSignal: null,
      centerX: 320,
      centerY: 180,
      deltaSec: 0.016,
      logicalHeight: 360,
      logicalWidth: 640,
      particleState: {
        reactiveEnv: 0.18,
        triggerEnv: 0.24,
        timeSec: 1.2,
      } as never,
      qualityPolicy: {
        tier: 'balanced',
        maxParticleCount: 480,
      } as never,
      reactiveEnergy: 0.18,
      runtime: {
        envelope: { kick: 0.12, drop: 0.06 },
      } as never,
      scale: 1,
      spectrumAttachment: null,
      templateDraft: {
        particlesEnabled: true,
        particlesMaxCount: 200,
        particlesVariant: 'dust',
        particlesStyle: 'glow',
        particlesDrift: 0,
        particlesSwirl: 0,
        particlesReactivity: 0.4,
        particlesOpacity: 0.6,
        particlesColor: '#ffffff',
        particlesReactColor: '#ffffff',
        particlesReactStrength: 0.5,
      } as never,
    })

    expect(result.gpuParticleSimulation).toEqual(
      expect.objectContaining({
        driftStrength: expect.any(Number),
        swirlStrength: expect.any(Number),
      }),
    )
    expect((result.gpuParticleSimulation?.driftStrength ?? 0) > 0).toBe(true)
    expect((result.gpuParticleSimulation?.swirlStrength ?? 0) > 0).toBe(true)
  })

  it('mixes toward the reactive color from sustained reactive energy even without a strong trigger spike', () => {
    mockUpdateParticleSimulation.mockReturnValue([{ id: 'particle-react-color' }])

    const result = buildParticleGpuState({
      audioSignal: {
        reactiveEnergy: 0.62,
        styleMotionDrive: 0.58,
        styleTriggerDrive: 0.14,
      } as never,
      centerX: 320,
      centerY: 180,
      deltaSec: 0.016,
      logicalHeight: 360,
      logicalWidth: 640,
      particleState: {
        reactiveEnv: 0.68,
        triggerEnv: 0.12,
        timeSec: 2.1,
      } as never,
      qualityPolicy: {
        tier: 'balanced',
        maxParticleCount: 480,
      } as never,
      reactiveEnergy: 0.62,
      runtime: {
        envelope: { kick: 0.12, drop: 0.08 },
      } as never,
      scale: 1,
      spectrumAttachment: null,
      templateDraft: {
        particlesEnabled: true,
        particlesMaxCount: 240,
        particlesVariant: 'classic',
        particlesStyle: 'dot',
        particlesDrift: 0.2,
        particlesSwirl: 0.2,
        particlesReactivity: 0.8,
        particlesOpacity: 0.7,
        particlesColor: '#0000ff',
        particlesReactColor: '#ff0000',
        particlesReactStrength: 1,
      } as never,
    })

    expect(result.gpuParticleSimulation).toEqual(
      expect.objectContaining({
        reactiveEnv: 0.68,
        triggerEnv: 0.12,
        baseBlue: 1,
        reactRed: 1,
        reactStrength: 1,
      }),
    )
    expect((result.gpuParticleSimulation?.red ?? 0)).toBeGreaterThan(0.6)
    expect((result.gpuParticleSimulation?.blue ?? 0)).toBeLessThan(0.4)
  })

  it('keeps swirl strength stable so audio travel does not turn into sideways back-and-forth motion', () => {
    mockUpdateParticleSimulation.mockReturnValue([{ id: 'particle-forward-only' }])

    const result = buildParticleGpuState({
      audioSignal: {
        reactiveEnergy: 0.72,
        styleMotionDrive: 0.68,
        styleTriggerDrive: 0.9,
      } as never,
      centerX: 320,
      centerY: 180,
      deltaSec: 0.016,
      logicalHeight: 360,
      logicalWidth: 640,
      particleState: {
        reactiveEnv: 0.75,
        triggerEnv: 0.92,
        timeSec: 3.4,
      } as never,
      qualityPolicy: {
        tier: 'balanced',
        maxParticleCount: 480,
      } as never,
      reactiveEnergy: 0.72,
      runtime: {
        envelope: { kick: 0.84, drop: 0.22 },
      } as never,
      scale: 1.5,
      spectrumAttachment: null,
      templateDraft: {
        particlesEnabled: true,
        particlesMaxCount: 240,
        particlesVariant: 'classic',
        particlesStyle: 'ring',
        particlesDrift: 0.25,
        particlesSwirl: 0.5,
        particlesReactivity: 0.8,
        particlesOpacity: 0.7,
        particlesColor: '#88ccff',
        particlesReactColor: '#ffffff',
        particlesReactStrength: 1,
      } as never,
    })

    expect(result.gpuParticleSimulation?.swirlStrength).toBeCloseTo((0.28 + 0.5 * 0.92) * 32 * 1.5, 5)
  })
})
