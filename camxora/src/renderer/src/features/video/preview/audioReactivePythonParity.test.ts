import {
  buildPythonParityTrace,
  resolvePythonParityBackgroundRawDrive,
  resolvePythonParityKickPower,
  resolvePythonParityLogoRawDrive,
  resolvePythonParityParticleRawDrive,
  resolvePythonParitySmoothedEnv,
} from '@/features/video/preview/audioReactivePythonParity'

describe('audioReactivePythonParity', () => {
  it('matches the Python-style squared kick envelope shaping', () => {
    expect(resolvePythonParityKickPower(0.5)).toBeCloseTo(0.25, 5)
    expect(resolvePythonParityKickPower(2)).toBe(1)
    expect(resolvePythonParityKickPower(-1)).toBe(0)
  })

  it('builds background, logo, and particle raw drives from bass plus weighted kick power', () => {
    expect(resolvePythonParityBackgroundRawDrive(0.28, 0.8)).toBeCloseTo(0.384, 5)
    expect(resolvePythonParityLogoRawDrive(0.28, 0.8)).toBeCloseTo(0.512, 5)
    expect(resolvePythonParityParticleRawDrive(0.28, 0.8)).toBeCloseTo(0.64, 5)
    expect(resolvePythonParityBackgroundRawDrive(0.72, 0.3)).toBeCloseTo(0.72, 5)
  })

  it('matches the Python smoothing rule and builds deterministic domain traces', () => {
    expect(resolvePythonParitySmoothedEnv(0.2, 0.8, 0.5)).toBeCloseTo(0.5, 5)

    const trace = buildPythonParityTrace({
      frames: [
        { bass: 0.1, kick: 0.1 },
        { bass: 0.4, kick: 0.7 },
      ],
      backgroundSmoothing: 0.5,
      logoSmoothing: 0.4,
      particleSmoothing: 0.35,
      particleTrigger: 'kick',
    })

    expect(trace.backgroundEnergy[0]).toBeCloseTo(0.05, 5)
    expect(trace.logoEnergy[1]).toBeGreaterThan(trace.logoEnergy[0])
    expect(trace.particleReactive[1]).toBeGreaterThan(trace.particleReactive[0])
    expect(trace.particleTrigger[1]).toBeGreaterThan(trace.particleTrigger[0])
  })
})
