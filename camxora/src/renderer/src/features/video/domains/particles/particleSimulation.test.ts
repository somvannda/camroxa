import { createParticleSimulationState, updateParticleSimulation } from '@/features/video/domains/particles/particleSimulation'

function createDraft() {
  return {
    particlesEnabled: true,
    particlesMaxCount: 200,
    particlesSpawnRate: 120,
    particlesLifetimeSec: 1.6,
    particlesSpeed: 1,
    particlesReactivity: 0.6,
    particlesSmoothing: 0.35,
    particlesSpawnMode: 'reactiveOnly',
    particlesSpawnTrigger: 'kick',
    particlesSpawnThreshold: 0.12,
    particlesVariant: 'classic',
    particlesSpawnArea: 'centerRing',
    particlesSizeJitter: 0,
    particlesDrift: 0,
    particlesSwirl: 0.1,
    particlesStyle: 'dot',
    particlesSize: 2,
    particlesOpacity: 0.35,
    particlesColor: '#ffffff',
    particlesReactColor: '#ff00ff',
    particlesReactStrength: 0.65,
  } as const
}

describe('particleSimulation shared reactive source', () => {
  it('drives particle sustain and spawning from the shared preview audio signal', () => {
    const state = createParticleSimulationState()
    const draft = createDraft()
    const reactiveTrace: number[] = []
    const triggerTrace: number[] = []

    const bassOnlyParticles = updateParticleSimulation(
      state,
      draft,
      320,
      180,
      640,
      360,
      80,
      1,
      0.1,
      0.16,
      {
        reactiveEnergy: 0.42,
        styleMotionDrive: 0.42,
        styleTriggerDrive: 0.04,
        averageEnergy: 0.28,
        averageTransient: 0.02,
        averageOnset: 0.02,
        kick: 0.04,
        drop: 0.02,
      } as never,
      { bassFast: 0.42, bassSlow: 0.32, kick: 0.04 },
    )
    reactiveTrace.push(state.reactiveEnv)
    triggerTrace.push(state.triggerEnv)

    expect(state.reactiveEnv).toBeGreaterThan(0.25)
    expect(state.triggerEnv).toBeLessThan(draft.particlesSpawnThreshold)
    expect(bassOnlyParticles.length).toBeGreaterThan(0)

    const kickParticles = updateParticleSimulation(
      state,
      draft,
      320,
      180,
      640,
      360,
      80,
      1,
      0.1,
      0.22,
      {
        reactiveEnergy: 0.72,
        styleMotionDrive: 0.68,
        styleTriggerDrive: 0.86,
        averageEnergy: 0.44,
        averageTransient: 0.58,
        averageOnset: 0.46,
        kick: 0.86,
        drop: 0.48,
      } as never,
      { bassFast: 0.18, bassSlow: 0.12, kick: 0.86 },
    )
    reactiveTrace.push(state.reactiveEnv)
    triggerTrace.push(state.triggerEnv)

    expect(state.triggerEnv).toBeGreaterThan(draft.particlesSpawnThreshold)
    expect(state.reactiveEnv).toBeGreaterThan(0.4)
    expect(kickParticles.length).toBeGreaterThan(0)
    expect(reactiveTrace[1]).toBeGreaterThan(reactiveTrace[0])
    expect(triggerTrace[1]).toBeGreaterThan(triggerTrace[0])
  })

  it('emits particles with enough travel speed to read as directional motion', () => {
    const state = createParticleSimulationState()
    const draft = {
      ...createDraft(),
      particlesSpawnMode: 'always',
      particlesSpawnRate: 180,
      particlesReactivity: 0.2,
      particlesSpeed: 1,
    }

    const particles = updateParticleSimulation(
      state,
      draft,
      320,
      180,
      640,
      360,
      90,
      1,
      0.16,
      0.24,
      {
        reactiveEnergy: 0.24,
        styleMotionDrive: 0.24,
        styleTriggerDrive: 0.18,
        averageEnergy: 0.2,
        averageTransient: 0.1,
        averageOnset: 0.08,
        kick: 0.18,
        drop: 0.12,
      } as never,
      { bassFast: 0.24, bassSlow: 0.2, kick: 0.18 },
    )

    expect(particles.length).toBeGreaterThan(0)
    expect(Math.max(...particles.map((particle) => particle.speed))).toBeGreaterThan(95)
  })

  it('keeps default particles large enough to read on screen', () => {
    const state = createParticleSimulationState()
    const particles = updateParticleSimulation(
      state,
      {
        ...createDraft(),
        particlesSpawnMode: 'always',
        particlesSpawnRate: 120,
        particlesStyle: 'dot',
        particlesSize: 2,
      },
      320,
      180,
      640,
      360,
      90,
      1,
      0.16,
      0.2,
      null,
      { bassFast: 0.2, bassSlow: 0.16, kick: 0.1 },
    )

    expect(particles.length).toBeGreaterThan(0)
    expect(Math.max(...particles.map((particle) => particle.halfWidth))).toBeGreaterThanOrEqual(1.9)
    expect(Math.max(...particles.map((particle) => particle.halfHeight))).toBeGreaterThanOrEqual(1.9)
  })

  it('uses distinct motion profiles for sparks versus drifting dust', () => {
    const sparkState = createParticleSimulationState()
    const dustState = createParticleSimulationState()
    const sparkParticles = updateParticleSimulation(
      sparkState,
      {
        ...createDraft(),
        particlesSpawnMode: 'always',
        particlesSpawnRate: 180,
        particlesVariant: 'classic',
        particlesStyle: 'spark',
      },
      320,
      180,
      640,
      360,
      90,
      1,
      0.16,
      0.3,
      null,
      { bassFast: 0.24, bassSlow: 0.2, kick: 0.18 },
    )
    const dustParticles = updateParticleSimulation(
      dustState,
      {
        ...createDraft(),
        particlesSpawnMode: 'always',
        particlesSpawnRate: 180,
        particlesVariant: 'dust',
        particlesStyle: 'glow',
      },
      320,
      180,
      640,
      360,
      90,
      1,
      0.16,
      0.3,
      null,
      { bassFast: 0.24, bassSlow: 0.2, kick: 0.18 },
    )

    expect(sparkParticles.length).toBeGreaterThan(0)
    expect(dustParticles.length).toBeGreaterThan(0)
    expect(
      sparkParticles.reduce((sum, particle) => sum + particle.speed, 0) / sparkParticles.length,
    ).toBeGreaterThan(
      dustParticles.reduce((sum, particle) => sum + particle.speed, 0) / dustParticles.length,
    )
    expect(
      dustParticles.reduce((sum, particle) => sum + particle.lifetimeSec, 0) / dustParticles.length,
    ).toBeGreaterThan(
      sparkParticles.reduce((sum, particle) => sum + particle.lifetimeSec, 0) / sparkParticles.length,
    )
  })

  it('keeps an explicit spark style on the spark render path even under the dust variant', () => {
    const state = createParticleSimulationState()
    const particles = updateParticleSimulation(
      state,
      {
        ...createDraft(),
        particlesSpawnMode: 'always',
        particlesSpawnRate: 120,
        particlesVariant: 'dust',
        particlesStyle: 'spark',
      },
      320,
      180,
      640,
      360,
      90,
      1,
      0.16,
      0.24,
      null,
      { bassFast: 0.2, bassSlow: 0.16, kick: 0.1 },
    )

    expect(particles.length).toBeGreaterThan(0)
    expect(particles.every((particle) => particle.style === 3)).toBe(true)
    expect(
      particles.every((particle) => particle.halfWidth > particle.halfHeight),
    ).toBe(true)
  })

  it('adds a trigger burst when reactive particles cross the beat threshold', () => {
    const state = createParticleSimulationState()
    const draft = {
      ...createDraft(),
      particlesMaxCount: 240,
      particlesSpawnMode: 'reactiveOnly',
      particlesSpawnTrigger: 'kick',
      particlesSpawnThreshold: 0.2,
      particlesStyle: 'spark',
    }

    const calmParticles = updateParticleSimulation(
      state,
      draft,
      320,
      180,
      640,
      360,
      90,
      1,
      0.1,
      0.12,
      {
        reactiveEnergy: 0.18,
        styleMotionDrive: 0.18,
        styleTriggerDrive: 0.08,
        averageEnergy: 0.14,
        averageTransient: 0.08,
        averageOnset: 0.08,
        kick: 0.08,
        drop: 0.04,
      } as never,
      { bassFast: 0.12, bassSlow: 0.1, kick: 0.08 },
    )

    const burstParticles = updateParticleSimulation(
      state,
      draft,
      320,
      180,
      640,
      360,
      90,
      1,
      0.1,
      0.46,
      {
        reactiveEnergy: 0.46,
        styleMotionDrive: 0.42,
        styleTriggerDrive: 0.92,
        averageEnergy: 0.36,
        averageTransient: 0.7,
        averageOnset: 0.62,
        kick: 0.92,
        drop: 0.5,
      } as never,
      { bassFast: 0.26, bassSlow: 0.2, kick: 0.92 },
    )

    expect(calmParticles.length).toBeGreaterThan(0)
    expect(burstParticles.length).toBeGreaterThan(12)
    expect(burstParticles.length).toBeGreaterThan(calmParticles.length)
  })

  it('keeps reactive particles spawning under high thresholds when audio support stays present', () => {
    const state = createParticleSimulationState()
    const draft = {
      ...createDraft(),
      particlesMaxCount: 320,
      particlesSpawnMode: 'reactiveOnly',
      particlesSpawnThreshold: 0.77,
      particlesLifetimeSec: 0.6,
      particlesSpawnRate: 220,
      particlesReactivity: 0.9,
    }

    const firstFrame = updateParticleSimulation(
      state,
      draft,
      320,
      180,
      640,
      360,
      90,
      1,
      0.12,
      0.08,
      {
        reactiveEnergy: 0.08,
        styleMotionDrive: 0.08,
        styleTriggerDrive: 0.04,
        averageEnergy: 0.06,
        averageTransient: 0.03,
        averageOnset: 0.03,
        kick: 0.04,
        drop: 0.03,
      } as never,
      { bassFast: 0.08, bassSlow: 0.06, kick: 0.04 },
    )
    const firstNewestSpawnSec = Math.max(...firstFrame.map((particle) => particle.spawnSec))

    let laterFrame = firstFrame
    for (let index = 0; index < 6; index += 1) {
      laterFrame = updateParticleSimulation(
        state,
        draft,
        320,
        180,
        640,
        360,
        90,
        1,
        0.12,
        0.08,
        {
          reactiveEnergy: 0.08,
          styleMotionDrive: 0.08,
          styleTriggerDrive: 0.04,
          averageEnergy: 0.06,
          averageTransient: 0.03,
          averageOnset: 0.03,
          kick: 0.04,
          drop: 0.03,
        } as never,
        { bassFast: 0.08, bassSlow: 0.06, kick: 0.04 },
      )
    }

    expect(laterFrame.length).toBeGreaterThan(0)
    expect(Math.max(...laterFrame.map((particle) => particle.spawnSec))).toBeGreaterThan(firstNewestSpawnSec)
  })

  it('makes freshly spawned particle travel react to stronger live audio drive', () => {
    const lowDriveState = createParticleSimulationState()
    const highDriveState = createParticleSimulationState()
    const draft = {
      ...createDraft(),
      particlesSpawnMode: 'always',
      particlesSpawnRate: 180,
      particlesSpeed: 1.4,
      particlesReactivity: 0.85,
    }

    const lowDriveParticles = updateParticleSimulation(
      lowDriveState,
      draft,
      320,
      180,
      640,
      360,
      90,
      1,
      0.16,
      0.06,
      {
        reactiveEnergy: 0.06,
        styleMotionDrive: 0.06,
        styleTriggerDrive: 0.03,
        averageEnergy: 0.05,
        averageTransient: 0.02,
        averageOnset: 0.02,
        kick: 0.03,
        drop: 0.02,
      } as never,
      { bassFast: 0.06, bassSlow: 0.05, kick: 0.03 },
    )

    const highDriveParticles = updateParticleSimulation(
      highDriveState,
      draft,
      320,
      180,
      640,
      360,
      90,
      1,
      0.16,
      0.62,
      {
        reactiveEnergy: 0.62,
        styleMotionDrive: 0.62,
        styleTriggerDrive: 0.78,
        averageEnergy: 0.44,
        averageTransient: 0.31,
        averageOnset: 0.28,
        kick: 0.78,
        drop: 0.24,
      } as never,
      { bassFast: 0.62, bassSlow: 0.44, kick: 0.78 },
    )

    expect(lowDriveParticles.length).toBeGreaterThan(0)
    expect(highDriveParticles.length).toBeGreaterThan(0)
    expect(
      highDriveParticles.reduce((sum, particle) => sum + particle.speed, 0) / highDriveParticles.length,
    ).toBeGreaterThan(
      lowDriveParticles.reduce((sum, particle) => sum + particle.speed, 0) / lowDriveParticles.length,
    )
  })

  it('keeps longer-lived particles from inheriting runaway travel speed', () => {
    const shortLifetimeState = createParticleSimulationState()
    const longLifetimeState = createParticleSimulationState()
    const baseDraft = {
      ...createDraft(),
      particlesSpawnMode: 'always',
      particlesSpawnRate: 180,
      particlesSpeed: 2.4,
      particlesReactivity: 0.55,
    }

    const shortLifetimeParticles = updateParticleSimulation(
      shortLifetimeState,
      {
        ...baseDraft,
        particlesLifetimeSec: 0.08,
      },
      320,
      180,
      640,
      360,
      90,
      1,
      0.16,
      0.24,
      null,
      { bassFast: 0.24, bassSlow: 0.18, kick: 0.12 },
    )
    const longLifetimeParticles = updateParticleSimulation(
      longLifetimeState,
      {
        ...baseDraft,
        particlesLifetimeSec: 6,
      },
      320,
      180,
      640,
      360,
      90,
      1,
      0.16,
      0.24,
      null,
      { bassFast: 0.24, bassSlow: 0.18, kick: 0.12 },
    )

    expect(shortLifetimeParticles.length).toBeGreaterThan(0)
    expect(longLifetimeParticles.length).toBeGreaterThan(0)
    expect(
      longLifetimeParticles.reduce((sum, particle) => sum + particle.speed, 0) / longLifetimeParticles.length,
    ).toBeLessThan(
      shortLifetimeParticles.reduce((sum, particle) => sum + particle.speed, 0) / shortLifetimeParticles.length,
    )
  })

  it('fills toward dense counts when max count and birth rate are pushed high', () => {
    const state = createParticleSimulationState()
    const draft = {
      ...createDraft(),
      particlesSpawnMode: 'always',
      particlesMaxCount: 2000,
      particlesSpawnRate: 1000,
      particlesLifetimeSec: 2.4,
      particlesSpeed: 1.1,
    }

    let particles = updateParticleSimulation(
      state,
      draft,
      320,
      180,
      640,
      360,
      90,
      1,
      0.1,
      0.18,
      null,
      { bassFast: 0.18, bassSlow: 0.14, kick: 0.08 },
    )

    for (let index = 0; index < 7; index += 1) {
      particles = updateParticleSimulation(
        state,
        draft,
        320,
        180,
        640,
        360,
        90,
        1,
        0.1,
        0.18,
        null,
        { bassFast: 0.18, bassSlow: 0.14, kick: 0.08 },
      )
    }

    expect(particles.length).toBeGreaterThanOrEqual(220)
    expect(particles.length).toBeLessThanOrEqual(draft.particlesMaxCount)
  })


  it('keeps reactive-only particles alive when support energy stays below but near the trigger threshold', () => {
    const state = createParticleSimulationState()
    const draft = {
      ...createDraft(),
      particlesMaxCount: 280,
      particlesSpawnMode: 'reactiveOnly',
      particlesSpawnTrigger: 'kick',
      particlesSpawnThreshold: 0.06,
      particlesStyle: 'spark',
      particlesSpeed: 4.2,
      particlesReactivity: 0.5,
    }

    const particles = updateParticleSimulation(
      state,
      draft,
      320,
      180,
      640,
      360,
      90,
      1,
      0.16,
      0,
      {
        reactiveEnergy: 0,
        styleMotionDrive: 0.03,
        styleTriggerDrive: 0.03,
        averageEnergy: 0.028,
        averageTransient: 0.02,
        averageOnset: 0.018,
        kick: 0.03,
        drop: 0.012,
      } as never,
      { bassFast: 0.028, bassSlow: 0.02, kick: 0.03 },
    )

    expect(state.triggerEnv).toBeLessThan(draft.particlesSpawnThreshold)
    expect(state.reactiveEnv).toBeGreaterThan(0.01)
    expect(particles.length).toBeGreaterThan(0)
  })
})
