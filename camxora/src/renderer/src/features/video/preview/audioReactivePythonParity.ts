function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value))
}

export type PythonParityFeatureFrame = {
  bass: number
  kick: number
}

export function resolvePythonParityKickPower(kick: number): number {
  const unitKick = clamp(kick, 0, 1)
  return unitKick * unitKick
}

export function resolvePythonParitySmoothedEnv(prev: number, target: number, smoothing: number): number {
  const s = clamp(smoothing, 0, 0.99)
  const t = clamp(target, 0, 1)
  return prev * s + t * (1 - s)
}

export function resolvePythonParityBackgroundRawDrive(bass: number, kick: number): number {
  return clamp(Math.max(clamp(bass, 0, 1), resolvePythonParityKickPower(kick) * 0.6), 0, 1)
}

export function resolvePythonParityLogoRawDrive(bass: number, kick: number): number {
  return clamp(Math.max(clamp(bass, 0, 1), resolvePythonParityKickPower(kick) * 0.8), 0, 1)
}

export function resolvePythonParityParticleRawDrive(bass: number, kick: number): number {
  return clamp(Math.max(clamp(bass, 0, 1), resolvePythonParityKickPower(kick)), 0, 1)
}

type BuildPythonParityTraceOptions = {
  frames: ReadonlyArray<PythonParityFeatureFrame>
  backgroundSmoothing: number
  logoSmoothing: number
  particleSmoothing: number
  particleTrigger: 'kick' | 'bass' | 'both'
}

export function buildPythonParityTrace({
  frames,
  backgroundSmoothing,
  logoSmoothing,
  particleSmoothing,
  particleTrigger,
}: BuildPythonParityTraceOptions): {
  backgroundEnergy: number[]
  logoEnergy: number[]
  particleReactive: number[]
  particleTrigger: number[]
} {
  let backgroundEnergy = 0
  let logoEnergy = 0
  let particleReactive = 0
  let particleTriggerEnv = 0

  const trace = {
    backgroundEnergy: [] as number[],
    logoEnergy: [] as number[],
    particleReactive: [] as number[],
    particleTrigger: [] as number[],
  }

  for (const frame of frames) {
    const backgroundRaw = resolvePythonParityBackgroundRawDrive(frame.bass, frame.kick)
    const logoRaw = resolvePythonParityLogoRawDrive(frame.bass, frame.kick)
    const particleRaw = resolvePythonParityParticleRawDrive(frame.bass, frame.kick)
    const kickPower = resolvePythonParityKickPower(frame.kick)
    const triggerRaw =
      particleTrigger === 'kick'
        ? kickPower
        : particleTrigger === 'bass'
          ? clamp(frame.bass, 0, 1)
          : Math.max(kickPower, clamp(frame.bass, 0, 1))

    backgroundEnergy = resolvePythonParitySmoothedEnv(backgroundEnergy, backgroundRaw, backgroundSmoothing)
    logoEnergy = resolvePythonParitySmoothedEnv(logoEnergy, logoRaw, logoSmoothing)
    particleReactive = resolvePythonParitySmoothedEnv(particleReactive, particleRaw, particleSmoothing)
    particleTriggerEnv = resolvePythonParitySmoothedEnv(particleTriggerEnv, triggerRaw, particleSmoothing)

    trace.backgroundEnergy.push(backgroundEnergy)
    trace.logoEnergy.push(logoEnergy)
    trace.particleReactive.push(particleReactive)
    trace.particleTrigger.push(particleTriggerEnv)
  }

  return trace
}
