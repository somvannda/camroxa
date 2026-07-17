import type {
  ParticleGpuPreparationRequest,
  ParticleGpuPreparationResult,
} from '@/features/video/domains/particles/particleGpuContract'
import { updateParticleSimulation } from '@/features/video/domains/particles/particleSimulation'
import { clampPreviewParticleCount } from '@/features/video/preview/previewQualityPolicy'
import { clamp, colorToNormalizedRgb } from '@/features/video/preview/previewUtils'
import { createVideoDebugSender } from '@/features/video/videoDiagnostics'

const sendParticleMotionDebug = createVideoDebugSender({
  sessionId: 'particle-motion-stuck',
  runId: 'pre-fix',
})

const sendParticleReactColorDebug = createVideoDebugSender({
  sessionId: 'particle-react-color',
  runId: 'pre-fix',
})

const sendParticleMissingDebug = createVideoDebugSender({
  sessionId: 'particle-missing',
  runId: 'pre-fix',
})

let lastParticleRuntimeDebugSecond = -1

function mixChannel(start: number, end: number, amount: number): number {
  return start * (1 - amount) + end * amount
}

function resolveParticleAudioMotionMode(value: string): number {
  const normalized = String(value || '').trim().toLowerCase()
  if (normalized === 'sizepulse' || normalized === 'size_pulse' || normalized === 'size-pulse') {
    return 0
  }
  if (normalized === 'travel') {
    return 1
  }
  return 2
}

function resolveParticleMotionBaselines(variant: string, style: string): {
  drift: number
  swirl: number
} {
  const normalizedVariant = String(variant || 'classic').trim().toLowerCase()
  if (normalizedVariant === 'dust') {
    return { drift: 0.32, swirl: 0.12 }
  }
  if (normalizedVariant === 'soap') {
    return { drift: 0.18, swirl: 0.34 }
  }
  if (normalizedVariant === 'bokeh') {
    return { drift: 0.24, swirl: 0.22 }
  }

  switch (String(style || 'dot').trim().toLowerCase()) {
    case 'spark':
      return { drift: 0.04, swirl: 0.05 }
    case 'glow':
      return { drift: 0.22, swirl: 0.12 }
    case 'ring':
      return { drift: 0.14, swirl: 0.28 }
    case 'bokeh':
      return { drift: 0.24, swirl: 0.22 }
    case 'dot':
    default:
      return { drift: 0.1, swirl: 0.12 }
  }
}

export function buildParticleGpuState({
  audioSignal,
  centerX,
  centerY,
  deltaSec,
  logicalHeight,
  logicalWidth,
  particleState,
  qualityPolicy,
  reactiveEnergy,
  runtime,
  scale,
  spectrumAttachment,
  templateDraft,
}: ParticleGpuPreparationRequest): ParticleGpuPreparationResult {
  const particlesStart = performance.now()
  const cappedMaxCount = templateDraft.particlesEnabled
    ? Math.max(1, clampPreviewParticleCount(templateDraft.particlesMaxCount, qualityPolicy))
    : 0
  const gpuParticles = updateParticleSimulation(
    particleState,
    {
      ...templateDraft,
      particlesMaxCount: cappedMaxCount,
    },
    centerX,
    centerY,
    logicalWidth,
    logicalHeight,
    Math.max(18 * scale, spectrumAttachment?.baseRadius ?? 0),
    scale,
    deltaSec,
    reactiveEnergy,
    audioSignal,
    runtime.envelope,
  )
  const baseColor = colorToNormalizedRgb(templateDraft.particlesColor)
  const reactColor = colorToNormalizedRgb(templateDraft.particlesReactColor)
  const reactiveEnv = clamp(particleState.reactiveEnv ?? 0, 0, 1)
  const triggerEnv = clamp(particleState.triggerEnv ?? 0, 0, 1)
  const motionBaselines = resolveParticleMotionBaselines(
    templateDraft.particlesVariant,
    templateDraft.particlesStyle,
  )
  const reactMix = clamp(
    Math.max(triggerEnv, reactiveEnv) * clamp(templateDraft.particlesReactStrength, 0, 1),
    0,
    1,
  )
  const gpuParticleSimulation = templateDraft.particlesEnabled
    ? {
        timeSec: Math.max(0, particleState.timeSec ?? 0),
        centerX,
        centerY,
        reactiveEnv,
        triggerEnv,
        driftStrength:
          (motionBaselines.drift + clamp(templateDraft.particlesDrift, 0, 1) * 0.9) * 28 * scale,
        swirlStrength:
          (motionBaselines.swirl + clamp(templateDraft.particlesSwirl, 0, 1) * 0.92) * 32 * scale,
        reactivity: clamp(templateDraft.particlesReactivity, 0, 1),
        audioTravelBoost: clamp(templateDraft.particlesAudioTravelBoost, 0, 4),
        audioMotionMode: resolveParticleAudioMotionMode(templateDraft.particlesAudioMotionMode),
        opacity: clamp(templateDraft.particlesOpacity, 0, 1),
        red: mixChannel(baseColor.red, reactColor.red, reactMix),
        green: mixChannel(baseColor.green, reactColor.green, reactMix),
        blue: mixChannel(baseColor.blue, reactColor.blue, reactMix),
        baseRed: baseColor.red,
        baseGreen: baseColor.green,
        baseBlue: baseColor.blue,
        reactRed: reactColor.red,
        reactGreen: reactColor.green,
        reactBlue: reactColor.blue,
        reactStrength: clamp(templateDraft.particlesReactStrength, 0, 1),
      }
    : null

  const debugSecond = Math.floor(Math.max(0, particleState.timeSec ?? 0))
  if (debugSecond !== lastParticleRuntimeDebugSecond) {
    const firstParticle = gpuParticles[0] ?? null
    // #region debug-point A:react-color-runtime
    sendParticleReactColorDebug({
      hypothesisId: 'A',
      location: 'particleGpuRuntime',
      msg: '[DEBUG] particle react-color runtime snapshot',
      data: {
        particlesEnabled: Boolean(templateDraft.particlesEnabled),
        particleCount: gpuParticles.length,
        particlesColor: String(templateDraft.particlesColor ?? ''),
        particlesReactColor: String(templateDraft.particlesReactColor ?? ''),
        particlesReactStrength: Number(Number(templateDraft.particlesReactStrength ?? 0).toFixed(3)),
        reactiveEnv: Number(reactiveEnv.toFixed(4)),
        triggerEnv: Number(triggerEnv.toFixed(4)),
        reactMix: Number(reactMix.toFixed(4)),
        baseRed: Number(baseColor.red.toFixed(4)),
        baseGreen: Number(baseColor.green.toFixed(4)),
        baseBlue: Number(baseColor.blue.toFixed(4)),
        reactRed: Number(reactColor.red.toFixed(4)),
        reactGreen: Number(reactColor.green.toFixed(4)),
        reactBlue: Number(reactColor.blue.toFixed(4)),
        packedReactStrength: Number((gpuParticleSimulation?.reactStrength ?? 0).toFixed(4)),
        packedBaseRed: Number((gpuParticleSimulation?.baseRed ?? 0).toFixed(4)),
        packedBaseGreen: Number((gpuParticleSimulation?.baseGreen ?? 0).toFixed(4)),
        packedBaseBlue: Number((gpuParticleSimulation?.baseBlue ?? 0).toFixed(4)),
        packedReactRed: Number((gpuParticleSimulation?.reactRed ?? 0).toFixed(4)),
        packedReactGreen: Number((gpuParticleSimulation?.reactGreen ?? 0).toFixed(4)),
        packedReactBlue: Number((gpuParticleSimulation?.reactBlue ?? 0).toFixed(4)),
        firstParticleSpeed: Number((firstParticle?.speed ?? 0).toFixed(3)),
        firstParticleLifetimeSec: Number((firstParticle?.lifetimeSec ?? 0).toFixed(3)),
      },
    })
    // #endregion
    // #region debug-point PM-A:particle-missing-runtime
    sendParticleMissingDebug({
      hypothesisId: 'A',
      location: 'particleGpuRuntime',
      msg: '[DEBUG] particle missing runtime snapshot',
      data: {
        particlesEnabled: Boolean(templateDraft.particlesEnabled),
        variant: String(templateDraft.particlesVariant ?? ''),
        style: String(templateDraft.particlesStyle ?? ''),
        particleCount: gpuParticles.length,
        reactiveEnv: Number(reactiveEnv.toFixed(4)),
        triggerEnv: Number(triggerEnv.toFixed(4)),
        audioTravelBoost: Number((gpuParticleSimulation?.audioTravelBoost ?? 0).toFixed(4)),
        audioMotionMode: Number((gpuParticleSimulation?.audioMotionMode ?? 0).toFixed(4)),
        firstParticle: firstParticle
          ? {
              speed: Number((firstParticle.speed ?? 0).toFixed(3)),
              dirX: Number((firstParticle.dirX ?? 0).toFixed(4)),
              dirY: Number((firstParticle.dirY ?? 0).toFixed(4)),
              spawnX: Number((firstParticle.spawnX ?? 0).toFixed(2)),
              spawnY: Number((firstParticle.spawnY ?? 0).toFixed(2)),
              halfWidth: Number((firstParticle.halfWidth ?? 0).toFixed(3)),
              halfHeight: Number((firstParticle.halfHeight ?? 0).toFixed(3)),
              opacity: Number((firstParticle.opacity ?? 0).toFixed(4)),
              styleIndex: Number((firstParticle.styleIndex ?? 0).toFixed(2)),
            }
          : null,
      },
    })
    // #endregion
    // #region debug-point D:particle-scale
    sendParticleMotionDebug({
      hypothesisId: 'C',
      location: 'particleGpuRuntime',
      msg: '[DEBUG] particle runtime snapshot',
      data: {
        particlesEnabled: Boolean(templateDraft.particlesEnabled),
        variant: String(templateDraft.particlesVariant ?? ''),
        style: String(templateDraft.particlesStyle ?? ''),
        spawnMode: String(templateDraft.particlesSpawnMode ?? ''),
        spawnArea: String(templateDraft.particlesSpawnArea ?? ''),
        requestedMaxCount: Math.round(Number(templateDraft.particlesMaxCount ?? 0)),
        cappedMaxCount,
        scale: Number(scale.toFixed(4)),
        logicalWidth: Number(logicalWidth.toFixed(2)),
        logicalHeight: Number(logicalHeight.toFixed(2)),
        centerX: Number(centerX.toFixed(2)),
        centerY: Number(centerY.toFixed(2)),
        particleCount: gpuParticles.length,
        reactiveEnergy: Number(reactiveEnergy.toFixed(4)),
        reactiveEnv: Number(reactiveEnv.toFixed(4)),
        triggerEnv: Number(triggerEnv.toFixed(4)),
        driftStrength: Number((gpuParticleSimulation?.driftStrength ?? 0).toFixed(3)),
        swirlStrength: Number((gpuParticleSimulation?.swirlStrength ?? 0).toFixed(3)),
        opacity: Number((gpuParticleSimulation?.opacity ?? 0).toFixed(3)),
        firstParticleSpeed: Number((firstParticle?.speed ?? 0).toFixed(3)),
        firstParticleDirX: Number((firstParticle?.dirX ?? 0).toFixed(3)),
        firstParticleDirY: Number((firstParticle?.dirY ?? 0).toFixed(3)),
        firstParticleLifetimeSec: Number((firstParticle?.lifetimeSec ?? 0).toFixed(3)),
        firstParticleSpawnX: Number((firstParticle?.spawnX ?? 0).toFixed(2)),
        firstParticleSpawnY: Number((firstParticle?.spawnY ?? 0).toFixed(2)),
        firstParticleHalfWidth: Number((firstParticle?.halfWidth ?? 0).toFixed(3)),
        firstParticleHalfHeight: Number((firstParticle?.halfHeight ?? 0).toFixed(3)),
      },
    })
    // #endregion
    lastParticleRuntimeDebugSecond = debugSecond
  }

  return {
    gpuParticles,
    gpuParticleSimulation,
    particlesMs: performance.now() - particlesStart,
  }
}
