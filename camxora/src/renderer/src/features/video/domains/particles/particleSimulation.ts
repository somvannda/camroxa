import type { PreviewParticleRuntimeDraft } from '@/features/video/core/contracts/previewDraftContracts'
import type { PreviewGpuAudioSignalFrame } from '@/features/video/core/contracts/previewGpuAudioSignalContract'
import type { WebGpuParticleInstance } from '@/features/video/webgpu/webgpuSpectrumRenderer'
import { clamp } from '@/features/video/preview/previewUtils'

type SpectrumReactiveEnvelope = {
  bassFast: number
  bassSlow: number
  kick: number
}

type PreviewParticle = {
  spawnX: number
  spawnY: number
  dirX: number
  dirY: number
  speed: number
  spawnSec: number
  lifetimeSec: number
  halfWidth: number
  halfHeight: number
  opacity: number
  styleIndex: number
  softness: number
  noiseSeed: number
}

export type ParticleSimulationState = {
  particles: PreviewParticle[]
  spawnCarry: number
  reactiveEnv: number
  timeSec: number
  triggerEnv: number
  previousTriggerEnv: number
  lastBurstSec: number
  seed: number
}

const PARTICLE_STYLE_INDEX_DOT = 0
const PARTICLE_STYLE_INDEX_GLOW = 1
const PARTICLE_STYLE_INDEX_RING = 2
const PARTICLE_STYLE_INDEX_SPARK = 3
const PARTICLE_STYLE_INDEX_BOKEH = 4

type ParticleBehaviorProfile = {
  outwardBias: number
  upwardBias: number
  speedMultiplier: number
  lifetimeMultiplier: number
  sizeMultiplier: number
  minFillRatio: number
  opacityFloor: number
  opacityCeil: number
}

export function createParticleSimulationState(): ParticleSimulationState {
  return {
    particles: [],
    spawnCarry: 0,
    reactiveEnv: 0,
    timeSec: 0,
    triggerEnv: 0,
    previousTriggerEnv: 0,
    lastBurstSec: -1,
    seed: 0x12345678,
  }
}

function nextParticleRandom(state: ParticleSimulationState): number {
  state.seed = (state.seed * 1664525 + 1013904223) >>> 0
  return state.seed / 0x100000000
}

function resolveParticleStyleIndex(variant: string, style: string): number {
  const normalizedVariant = String(variant || 'classic').trim().toLowerCase()
  const normalizedStyle = String(style || 'dot').trim().toLowerCase()

  // Respect an explicit spark selection so the user-facing style control
  // cannot be silently overridden by the broader motion variant.
  if (normalizedStyle === 'spark') {
    return PARTICLE_STYLE_INDEX_SPARK
  }

  if (normalizedVariant === 'bokeh') {
    return PARTICLE_STYLE_INDEX_BOKEH
  }
  if (normalizedVariant === 'soap') {
    return PARTICLE_STYLE_INDEX_RING
  }
  if (normalizedVariant === 'dust') {
    return PARTICLE_STYLE_INDEX_GLOW
  }

  switch (normalizedStyle) {
    case 'glow':
      return PARTICLE_STYLE_INDEX_GLOW
    case 'ring':
      return PARTICLE_STYLE_INDEX_RING
    case 'spark':
      return PARTICLE_STYLE_INDEX_SPARK
    case 'bokeh':
      return PARTICLE_STYLE_INDEX_BOKEH
    case 'dot':
    default:
      return PARTICLE_STYLE_INDEX_DOT
  }
}

function resolveParticleBehaviorProfile(styleIndex: number): ParticleBehaviorProfile {
  switch (styleIndex) {
    case PARTICLE_STYLE_INDEX_GLOW:
      return {
        outwardBias: 0.28,
        upwardBias: 0.72,
        speedMultiplier: 0.88,
        lifetimeMultiplier: 1.45,
        sizeMultiplier: 1.16,
        minFillRatio: 0.18,
        opacityFloor: 0.72,
        opacityCeil: 1,
      }
    case PARTICLE_STYLE_INDEX_RING:
      return {
        outwardBias: 0.34,
        upwardBias: 0.56,
        speedMultiplier: 0.82,
        lifetimeMultiplier: 1.7,
        sizeMultiplier: 1.22,
        minFillRatio: 0.1,
        opacityFloor: 0.68,
        opacityCeil: 0.96,
      }
    case PARTICLE_STYLE_INDEX_SPARK:
      return {
        outwardBias: 0.82,
        upwardBias: 0.12,
        speedMultiplier: 1.9,
        lifetimeMultiplier: 0.62,
        sizeMultiplier: 0.92,
        minFillRatio: 0.05,
        opacityFloor: 0.84,
        opacityCeil: 1,
      }
    case PARTICLE_STYLE_INDEX_BOKEH:
      return {
        outwardBias: 0.24,
        upwardBias: 0.42,
        speedMultiplier: 0.76,
        lifetimeMultiplier: 1.9,
        sizeMultiplier: 1.34,
        minFillRatio: 0.12,
        opacityFloor: 0.66,
        opacityCeil: 0.94,
      }
    case PARTICLE_STYLE_INDEX_DOT:
    default:
      return {
        outwardBias: 0.54,
        upwardBias: 0.24,
        speedMultiplier: 1.18,
        lifetimeMultiplier: 1,
        sizeMultiplier: 1.2,
        minFillRatio: 0.11,
        opacityFloor: 0.72,
        opacityCeil: 0.98,
      }
  }
}

function blendNormalizedDirection(
  baseX: number,
  baseY: number,
  addX: number,
  addY: number,
  amount: number,
): { x: number; y: number } {
  const mixAmount = clamp(amount, 0, 1)
  const rawX = baseX * (1 - mixAmount) + addX * mixAmount
  const rawY = baseY * (1 - mixAmount) + addY * mixAmount
  const length = Math.max(0.0001, Math.hypot(rawX, rawY))
  return {
    x: rawX / length,
    y: rawY / length,
  }
}

function resolveParticleTriggerValue(trigger: string, envelope: SpectrumReactiveEnvelope): number {
  const kick = clamp(envelope.kick, 0, 1)
  const bass = clamp(envelope.bassFast, 0, 1)
  switch (String(trigger || 'both').trim().toLowerCase()) {
    case 'kick':
      return kick
    case 'bass':
      return bass
    default:
      return Math.max(kick, bass)
  }
}

function resolveParticleReactiveSupportValue(
  audioSignal: PreviewGpuAudioSignalFrame | null,
  reactiveEnergy: number,
  envelope: SpectrumReactiveEnvelope,
): number {
  return clamp(
    Math.max(
      reactiveEnergy,
      audioSignal?.reactiveEnergy ?? 0,
      audioSignal?.styleMotionDrive ?? 0,
      audioSignal?.averageEnergy ?? 0,
      envelope.bassFast,
    ),
    0,
    1,
  )
}

function resolveParticleSignalTriggerValue(
  trigger: string,
  audioSignal: PreviewGpuAudioSignalFrame | null,
  reactiveSupport: number,
  envelope: SpectrumReactiveEnvelope,
): number {
  const kickLike = Math.max(audioSignal?.styleTriggerDrive ?? 0, audioSignal?.kick ?? 0, envelope.kick)
  const sustainLike = Math.max(
    reactiveSupport,
    audioSignal?.styleMotionDrive ?? 0,
    audioSignal?.averageTransient ?? 0,
    audioSignal?.averageOnset ?? 0,
    clamp(envelope.bassFast, 0, 1),
  )
  switch (String(trigger || 'both').trim().toLowerCase()) {
    case 'kick':
      return clamp(kickLike, 0, 1)
    case 'bass':
      return clamp(sustainLike, 0, 1)
    default:
      return clamp(Math.max(kickLike, sustainLike), 0, 1)
  }
}

function buildParticleExtents(
  sizePx: number,
  styleIndex: number,
): { halfWidth: number; halfHeight: number; softness: number } {
  switch (styleIndex) {
    case PARTICLE_STYLE_INDEX_GLOW:
      return { halfWidth: sizePx * 0.92, halfHeight: sizePx * 0.92, softness: 0.48 }
    case PARTICLE_STYLE_INDEX_RING:
      return { halfWidth: sizePx * 0.9, halfHeight: sizePx * 0.9, softness: 0.18 }
    case PARTICLE_STYLE_INDEX_SPARK:
      return { halfWidth: sizePx * 2.1, halfHeight: Math.max(1.05, sizePx * 0.32), softness: 0.16 }
    case PARTICLE_STYLE_INDEX_BOKEH:
      return { halfWidth: sizePx * 1.08, halfHeight: sizePx * 1.08, softness: 0.55 }
    case PARTICLE_STYLE_INDEX_DOT:
    default:
      return { halfWidth: sizePx * 0.82, halfHeight: sizePx * 0.82, softness: 0.24 }
  }
}

function resolveParticleBurstCount(
  styleIndex: number,
  maxCount: number,
  triggerEnv: number,
): number {
  const intensity = clamp(triggerEnv, 0, 1)
  switch (styleIndex) {
    case PARTICLE_STYLE_INDEX_SPARK:
      return Math.min(maxCount, Math.max(10, Math.round(10 + intensity * 28)))
    case PARTICLE_STYLE_INDEX_GLOW:
      return Math.min(maxCount, Math.max(6, Math.round(6 + intensity * 12)))
    case PARTICLE_STYLE_INDEX_RING:
      return Math.min(maxCount, Math.max(5, Math.round(5 + intensity * 10)))
    case PARTICLE_STYLE_INDEX_BOKEH:
      return Math.min(maxCount, Math.max(4, Math.round(4 + intensity * 8)))
    case PARTICLE_STYLE_INDEX_DOT:
    default:
      return Math.min(maxCount, Math.max(8, Math.round(8 + intensity * 16)))
  }
}

function resolveLifetimeMotionScale(lifetimeSec: number): number {
  const safeLifetimeSec = Math.max(0.08, lifetimeSec)
  return clamp(Math.pow(0.75 / safeLifetimeSec, 0.7), 0.18, 1.4)
}

function spawnPreviewParticle(
  state: ParticleSimulationState,
  draft: PreviewParticleRuntimeDraft,
  centerX: number,
  centerY: number,
  width: number,
  height: number,
  anchorRadius: number,
  scale: number,
  liveDrive: number,
): PreviewParticle {
  const random = () => nextParticleRandom(state)
  const variantStyle = resolveParticleStyleIndex(draft.particlesVariant, draft.particlesStyle)
  const behavior = resolveParticleBehaviorProfile(variantStyle)
  const clampedLiveDrive = clamp(liveDrive, 0, 1)
  const angle = random() * Math.PI * 2
  const edgeChoice = random()
  let x = centerX
  let y = centerY
  let dirX = Math.cos(angle)
  let dirY = Math.sin(angle)

  switch (draft.particlesSpawnArea) {
    case 'screenCenter': {
      const radius = Math.max(12 * scale, Math.min(width, height) * 0.05 * random())
      x = centerX + Math.cos(angle) * radius
      y = centerY + Math.sin(angle) * radius
      break
    }
    case 'screenRandom': {
      x = random() * width
      y = random() * height
      const toCenterX = centerX - x
      const toCenterY = centerY - y
      const distance = Math.max(1, Math.hypot(toCenterX, toCenterY))
      dirX = toCenterX / distance
      dirY = toCenterY / distance
      break
    }
    case 'bottom': {
      const spread = width * 0.38
      x = centerX + (random() * 2 - 1) * spread
      y = height + 18 * scale
      dirX = (random() * 2 - 1) * 0.35
      dirY = -1
      break
    }
    case 'edges': {
      if (edgeChoice < 0.25) {
        x = random() * width
        y = -18 * scale
      } else if (edgeChoice < 0.5) {
        x = width + 18 * scale
        y = random() * height
      } else if (edgeChoice < 0.75) {
        x = random() * width
        y = height + 18 * scale
      } else {
        x = -18 * scale
        y = random() * height
      }
      const toCenterX = centerX - x
      const toCenterY = centerY - y
      const distance = Math.max(1, Math.hypot(toCenterX, toCenterY))
      dirX = toCenterX / distance
      dirY = toCenterY / distance
      break
    }
    case 'full': {
      const radius = anchorRadius + random() * Math.min(width, height) * 0.32
      x = centerX + Math.cos(angle) * radius
      y = centerY + Math.sin(angle) * radius
      break
    }
    case 'centerRing':
    default: {
      const radius = anchorRadius + (random() * 2 - 1) * Math.max(10 * scale, anchorRadius * 0.1)
      x = centerX + Math.cos(angle) * radius
      y = centerY + Math.sin(angle) * radius
      break
    }
  }

  const outwardX = x - centerX
  const outwardY = y - centerY
  const outwardLength = Math.max(0.0001, Math.hypot(outwardX, outwardY))
  const normalizedOutwardX = outwardX / outwardLength
  const normalizedOutwardY = outwardY / outwardLength
  const directionLength = Math.max(1, Math.hypot(dirX, dirY))
  const radialBlend = blendNormalizedDirection(
    dirX / directionLength,
    dirY / directionLength,
    normalizedOutwardX,
    normalizedOutwardY,
    behavior.outwardBias,
  )
  const upwardBlend = blendNormalizedDirection(
    radialBlend.x,
    radialBlend.y,
    0,
    -1,
    behavior.upwardBias,
  )
  const sizeJitter = 1 + (random() * 2 - 1) * clamp(draft.particlesSizeJitter, 0, 1)
  const lifetimeSec = Math.max(
    0.08,
    draft.particlesLifetimeSec * behavior.lifetimeMultiplier * (0.82 + random() * 0.4),
  )
  const particleSizePx = Math.max(
    2.4,
    draft.particlesSize * scale * sizeJitter * behavior.sizeMultiplier,
  )
  const extents = buildParticleExtents(particleSizePx, variantStyle)
  const speedBoost =
    64 +
    clamp(draft.particlesReactivity, 0, 1) * 220 +
    clampedLiveDrive * (110 + clamp(draft.particlesReactivity, 0, 1) * 170)
  const lifetimeMotionScale = resolveLifetimeMotionScale(lifetimeSec)
  const speed = Math.max(
    18,
    draft.particlesSpeed *
      speedBoost *
      behavior.speedMultiplier *
      lifetimeMotionScale *
      scale *
      (0.82 + random() * 0.72),
  )

  return {
    spawnX: x,
    spawnY: y,
    dirX: upwardBlend.x,
    dirY: upwardBlend.y,
    speed,
    spawnSec: state.timeSec,
    lifetimeSec,
    halfWidth: extents.halfWidth,
    halfHeight: extents.halfHeight,
    opacity: behavior.opacityFloor + random() * Math.max(0, behavior.opacityCeil - behavior.opacityFloor),
    styleIndex: variantStyle,
    softness: extents.softness,
    noiseSeed: random(),
  }
}

export function updateParticleSimulation(
  state: ParticleSimulationState,
  draft: PreviewParticleRuntimeDraft,
  centerX: number,
  centerY: number,
  width: number,
  height: number,
  anchorRadius: number,
  scale: number,
  deltaSec: number,
  reactiveEnergy: number,
  audioSignal: PreviewGpuAudioSignalFrame | null,
  envelope: SpectrumReactiveEnvelope,
): WebGpuParticleInstance[] {
  if (!draft.particlesEnabled) {
    state.particles = []
    state.spawnCarry = 0
    state.reactiveEnv = 0
    state.timeSec = 0
    state.triggerEnv = 0
    state.previousTriggerEnv = 0
    state.lastBurstSec = -1
    return []
  }

  state.timeSec += Math.max(0, deltaSec)

  const particleReactiveTarget = resolveParticleReactiveSupportValue(audioSignal, reactiveEnergy, envelope)
  const triggerRaw =
    audioSignal || reactiveEnergy > 0
      ? resolveParticleSignalTriggerValue(
          draft.particlesSpawnTrigger,
          audioSignal,
          particleReactiveTarget,
          envelope,
        )
      : resolveParticleTriggerValue(draft.particlesSpawnTrigger, envelope)
  state.reactiveEnv = state.reactiveEnv * draft.particlesSmoothing + particleReactiveTarget * (1 - draft.particlesSmoothing)
  state.triggerEnv = state.triggerEnv * draft.particlesSmoothing + triggerRaw * (1 - draft.particlesSmoothing)

  if (state.particles.length) {
    const nowSec = state.timeSec
    state.particles = state.particles.filter(
      (particle) => nowSec - particle.spawnSec < particle.lifetimeSec,
    )
  }

  const triggerThreshold = clamp(draft.particlesSpawnThreshold, 0, 1)
  const reactiveSupport = Math.max(state.reactiveEnv, particleReactiveTarget)
  const liveDrive = Math.max(reactiveSupport, state.triggerEnv)
  const reactiveOnlyBurstGate = state.triggerEnv >= triggerThreshold
  const reactiveOnlySustainGate = reactiveSupport >= Math.min(0.04, Math.max(0.015, triggerThreshold * 0.35))
  const spawnActive =
    draft.particlesSpawnMode !== 'reactiveOnly' || reactiveOnlyBurstGate || reactiveOnlySustainGate
  const spawnRate = spawnActive
    ? draft.particlesSpawnRate *
      (draft.particlesSpawnMode === 'always'
        ? 0.35 + reactiveSupport * (1.5 + draft.particlesReactivity * 2.2)
        : reactiveOnlyBurstGate
          ? 0.45 + reactiveSupport * (2.8 + draft.particlesReactivity * 4.4)
          : 0.24 + reactiveSupport * (1.45 + draft.particlesReactivity * 2.7))
    : 0

  const maxCount = Math.max(0, Math.round(draft.particlesMaxCount))
  if (maxCount <= 0) {
    state.particles = []
    state.spawnCarry = 0
    state.previousTriggerEnv = state.triggerEnv
    return []
  }

  const styleIndex = resolveParticleStyleIndex(draft.particlesVariant, draft.particlesStyle)
  const behaviorProfile = resolveParticleBehaviorProfile(styleIndex)
  const crossedTrigger =
    state.triggerEnv >= triggerThreshold &&
    state.previousTriggerEnv < triggerThreshold &&
    state.timeSec - state.lastBurstSec > 0.08
  if (crossedTrigger) {
    const burstCount = resolveParticleBurstCount(styleIndex, maxCount, state.triggerEnv)
    for (let index = 0; index < burstCount; index += 1) {
      state.particles.push(
        spawnPreviewParticle(state, draft, centerX, centerY, width, height, anchorRadius, scale, liveDrive),
      )
    }
    state.lastBurstSec = state.timeSec
  }

  if (state.particles.length === 0 && spawnActive) {
    const initialCount = Math.min(
      maxCount,
      Math.max(12, Math.round(maxCount * 0.06)),
      Math.max(12, Math.round(draft.particlesSpawnRate * 0.12)),
    )
    for (let index = 0; index < initialCount; index += 1) {
      state.particles.push(
        spawnPreviewParticle(state, draft, centerX, centerY, width, height, anchorRadius, scale, liveDrive),
      )
    }
  }

  if (spawnActive) {
    const fillTarget = Math.min(
      maxCount,
      Math.max(
        styleIndex === PARTICLE_STYLE_INDEX_SPARK ? 8 : 12,
        Math.round(maxCount * behaviorProfile.minFillRatio * (0.55 + reactiveSupport * 1.15)),
        Math.round(
          draft.particlesSpawnRate *
            (draft.particlesSpawnMode === 'always'
              ? 0.22
              : reactiveOnlyBurstGate
                ? 0.18
                : 0.14),
        ),
      ),
    )
    if (state.particles.length < fillTarget) {
      const missingCount = fillTarget - state.particles.length
      for (let index = 0; index < missingCount; index += 1) {
        state.particles.push(
          spawnPreviewParticle(state, draft, centerX, centerY, width, height, anchorRadius, scale, liveDrive),
        )
      }
    }
  }

  state.spawnCarry += Math.max(0, spawnRate) * deltaSec
  let spawnCount = Math.floor(state.spawnCarry)
  state.spawnCarry -= spawnCount
  spawnCount = Math.max(0, spawnCount)

  for (let index = 0; index < spawnCount; index += 1) {
    state.particles.push(
      spawnPreviewParticle(state, draft, centerX, centerY, width, height, anchorRadius, scale, liveDrive),
    )
  }

  if (state.particles.length > maxCount) {
    state.particles.splice(0, state.particles.length - maxCount)
  }

  state.previousTriggerEnv = state.triggerEnv

  return state.particles.map((particle) => ({
    spawnX: particle.spawnX,
    spawnY: particle.spawnY,
    dirX: particle.dirX,
    dirY: particle.dirY,
    halfWidth: particle.halfWidth,
    halfHeight: particle.halfHeight,
    speed: particle.speed,
    spawnSec: particle.spawnSec,
    lifetimeSec: particle.lifetimeSec,
    opacity: particle.opacity,
    style: particle.styleIndex,
    softness: particle.softness,
    noiseSeed: particle.noiseSeed,
  }))
}
