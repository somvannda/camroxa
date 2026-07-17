import { normalizeColor, toBoolean, toNumber, toRecord, toStringValue } from '@/features/video/domains/shared/templateValueUtils'

export const PARTICLE_SPAWN_MODE_OPTIONS = [
  { value: 'always', label: 'Always' },
  { value: 'reactiveOnly', label: 'Audio Reactive Only' },
] as const

export const PARTICLE_SPAWN_TRIGGER_OPTIONS = [
  { value: 'both', label: 'Kick or Bass' },
  { value: 'kick', label: 'Kick' },
  { value: 'bass', label: 'Bass' },
] as const

export const PARTICLE_VARIANT_OPTIONS = [
  { value: 'classic', label: 'Classic' },
  { value: 'bokeh', label: 'Bokeh Bubbles' },
  { value: 'soap', label: 'Soap Bubble' },
  { value: 'dust', label: 'Floating Dust' },
] as const

export const PARTICLE_SPAWN_AREA_OPTIONS = [
  { value: 'centerRing', label: 'Halo Around Core' },
  { value: 'screenCenter', label: 'Screen Center' },
  { value: 'screenRandom', label: 'Random Screen' },
  { value: 'bottom', label: 'Bottom Arc' },
  { value: 'edges', label: 'Frame Edges' },
  { value: 'full', label: 'Wide Halo Field' },
] as const

export const PARTICLE_STYLE_OPTIONS = [
  { value: 'dot', label: 'Dot' },
  { value: 'glow', label: 'Soft Glow' },
  { value: 'ring', label: 'Ring' },
  { value: 'spark', label: 'Spark' },
  { value: 'bokeh', label: 'Bokeh' },
] as const

export const PARTICLE_AUDIO_MOTION_MODE_OPTIONS = [
  { value: 'both', label: 'Size Pulse + Travel' },
  { value: 'travel', label: 'Travel Only' },
  { value: 'sizePulse', label: 'Size Pulse Only' },
] as const

export const PARTICLE_MOTION_PRESETS = [
  {
    value: 'embers',
    label: 'Embers',
    description: 'Fast reactive sparks that burst away from the ring on beats.',
  },
  {
    value: 'dust_field',
    label: 'Dust Field',
    description: 'Slow atmospheric particles that drift and breathe through the frame.',
  },
  {
    value: 'dreamy_bokeh',
    label: 'Dreamy Bokeh',
    description: 'Large floating light discs with soft upward motion.',
  },
  {
    value: 'soap_orbit',
    label: 'Soap Orbit',
    description: 'Round suspended bubbles that orbit and rise around the core.',
  },
  {
    value: 'energy_sparks',
    label: 'Energy Sparks',
    description: 'Aggressive electrical streaks with strong audio-driven bursts.',
  },
  {
    value: 'flash_sparks',
    label: 'Flash Sparks',
    description: 'Instant reactive bursts that flash to the react color then fade out quickly.',
  },
] as const

export type ParticleMotionPresetId = (typeof PARTICLE_MOTION_PRESETS)[number]['value']

export type ParticleSettingsState = {
  particlesEnabled: boolean
  particlesMaxCount: number
  particlesSpawnRate: number
  particlesLifetimeSec: number
  particlesSpeed: number
  particlesReactivity: number
  particlesAudioTravelBoost: number
  particlesAudioMotionMode: string
  particlesSmoothing: number
  particlesSpawnMode: string
  particlesSpawnTrigger: string
  particlesSpawnThreshold: number
  particlesVariant: string
  particlesSpawnArea: string
  particlesSizeJitter: number
  particlesDrift: number
  particlesSwirl: number
  particlesStyle: string
  particlesSize: number
  particlesOpacity: number
  particlesColor: string
  particlesReactColor: string
  particlesReactStrength: number
}

export const PARTICLE_MOTION_PRESET_FIELD_KEYS = [
  'particlesEnabled',
  'particlesVariant',
  'particlesStyle',
  'particlesSpawnArea',
  'particlesSpawnMode',
  'particlesSpeed',
  'particlesLifetimeSec',
  'particlesSize',
  'particlesOpacity',
  'particlesReactivity',
  'particlesAudioMotionMode',
  'particlesAudioTravelBoost',
  'particlesColor',
  'particlesReactColor',
  'particlesMaxCount',
  'particlesSpawnRate',
  'particlesSmoothing',
  'particlesSpawnTrigger',
  'particlesSizeJitter',
  'particlesDrift',
  'particlesSwirl',
  'particlesReactStrength',
  'particlesSpawnThreshold',
] as const satisfies ReadonlyArray<keyof ParticleSettingsState>

export type ParticleMotionPresetPatch = Pick<
  ParticleSettingsState,
  (typeof PARTICLE_MOTION_PRESET_FIELD_KEYS)[number]
>

const PARTICLE_MOTION_PRESET_PATCHES: Record<ParticleMotionPresetId, ParticleMotionPresetPatch> = {
  embers: {
    particlesEnabled: true,
    particlesVariant: 'classic',
    particlesStyle: 'spark',
    particlesSpawnArea: 'centerRing',
    particlesSpawnMode: 'reactiveOnly',
    particlesSpeed: 3.6,
    particlesLifetimeSec: 1.15,
    particlesSize: 4.6,
    particlesOpacity: 0.9,
    particlesReactivity: 0.42,
    particlesAudioMotionMode: 'both',
    particlesAudioTravelBoost: 1,
    particlesColor: '#ffd36b',
    particlesReactColor: '#fff4d6',
    particlesMaxCount: 480,
    particlesSpawnRate: 340,
    particlesSmoothing: 0.14,
    particlesSpawnTrigger: 'both',
    particlesSizeJitter: 0.48,
    particlesDrift: 0.14,
    particlesSwirl: 0.1,
    particlesReactStrength: 0.78,
    particlesSpawnThreshold: 0.03,
  },
  dust_field: {
    particlesEnabled: true,
    particlesVariant: 'dust',
    particlesStyle: 'glow',
    particlesSpawnArea: 'full',
    particlesSpawnMode: 'always',
    particlesSpeed: 1.1,
    particlesLifetimeSec: 5.2,
    particlesSize: 8.2,
    particlesOpacity: 0.48,
    particlesReactivity: 0.22,
    particlesAudioMotionMode: 'both',
    particlesAudioTravelBoost: 1,
    particlesColor: '#f7ede2',
    particlesReactColor: '#fff8ef',
    particlesMaxCount: 920,
    particlesSpawnRate: 320,
    particlesSmoothing: 0.58,
    particlesSpawnTrigger: 'bass',
    particlesSizeJitter: 0.82,
    particlesDrift: 0.52,
    particlesSwirl: 0.22,
    particlesReactStrength: 0.42,
    particlesSpawnThreshold: 0.08,
  },
  dreamy_bokeh: {
    particlesEnabled: true,
    particlesVariant: 'bokeh',
    particlesStyle: 'bokeh',
    particlesSpawnArea: 'screenCenter',
    particlesSpawnMode: 'always',
    particlesSpeed: 1.12,
    particlesLifetimeSec: 6.2,
    particlesSize: 15.4,
    particlesOpacity: 0.5,
    particlesReactivity: 0.18,
    particlesAudioMotionMode: 'both',
    particlesAudioTravelBoost: 1,
    particlesColor: '#bfe7ff',
    particlesReactColor: '#ffffff',
    particlesMaxCount: 360,
    particlesSpawnRate: 170,
    particlesSmoothing: 0.72,
    particlesSpawnTrigger: 'bass',
    particlesSizeJitter: 0.72,
    particlesDrift: 0.34,
    particlesSwirl: 0.28,
    particlesReactStrength: 0.48,
    particlesSpawnThreshold: 0.1,
  },
  soap_orbit: {
    particlesEnabled: true,
    particlesVariant: 'soap',
    particlesStyle: 'ring',
    particlesSpawnArea: 'centerRing',
    particlesSpawnMode: 'always',
    particlesSpeed: 1.28,
    particlesLifetimeSec: 5.8,
    particlesSize: 10.2,
    particlesOpacity: 0.5,
    particlesReactivity: 0.22,
    particlesAudioMotionMode: 'both',
    particlesAudioTravelBoost: 1,
    particlesColor: '#d6f4ff',
    particlesReactColor: '#ffffff',
    particlesMaxCount: 320,
    particlesSpawnRate: 150,
    particlesSmoothing: 0.62,
    particlesSpawnTrigger: 'bass',
    particlesSizeJitter: 0.58,
    particlesDrift: 0.22,
    particlesSwirl: 0.58,
    particlesReactStrength: 0.5,
    particlesSpawnThreshold: 0.08,
  },
  energy_sparks: {
    particlesEnabled: true,
    particlesVariant: 'classic',
    particlesStyle: 'spark',
    particlesSpawnArea: 'centerRing',
    particlesSpawnMode: 'reactiveOnly',
    particlesSpeed: 5.4,
    particlesLifetimeSec: 0.84,
    particlesSize: 3.8,
    particlesOpacity: 1,
    particlesReactivity: 0.5,
    particlesAudioMotionMode: 'both',
    particlesAudioTravelBoost: 1,
    particlesColor: '#64e5ff',
    particlesReactColor: '#ffffff',
    particlesMaxCount: 680,
    particlesSpawnRate: 560,
    particlesSmoothing: 0.08,
    particlesSpawnTrigger: 'kick',
    particlesSizeJitter: 0.42,
    particlesDrift: 0.08,
    particlesSwirl: 0.14,
    particlesReactStrength: 0.92,
    particlesSpawnThreshold: 0.02,
  },
  flash_sparks: {
    particlesEnabled: true,
    particlesVariant: 'classic',
    particlesStyle: 'spark',
    particlesSpawnArea: 'centerRing',
    particlesSpawnMode: 'reactiveOnly',
    particlesSpeed: 5.8,
    particlesLifetimeSec: 0.38,
    particlesSize: 3.6,
    particlesOpacity: 1,
    particlesReactivity: 0.62,
    particlesAudioMotionMode: 'both',
    particlesAudioTravelBoost: 1,
    particlesColor: '#64e5ff',
    particlesReactColor: '#ffffff',
    particlesMaxCount: 320,
    particlesSpawnRate: 760,
    particlesSmoothing: 0.04,
    particlesSpawnTrigger: 'kick',
    particlesSizeJitter: 0.38,
    particlesDrift: 0.05,
    particlesSwirl: 0.06,
    particlesReactStrength: 1,
    particlesSpawnThreshold: 0.16,
  },
}

export function buildParticleMotionPresetPatch(
  presetId: ParticleMotionPresetId,
): ParticleMotionPresetPatch {
  return PARTICLE_MOTION_PRESET_PATCHES[presetId]
}

export function buildParticleSettingsState(template: Record<string, unknown>): ParticleSettingsState {
  const particlesSettings = toRecord(template.particlesSettings)

  return {
    particlesEnabled: toBoolean(particlesSettings.enabled, true),
    particlesMaxCount: toNumber(particlesSettings.maxCount, 200),
    particlesSpawnRate: toNumber(particlesSettings.spawnRate, 100),
    particlesLifetimeSec: toNumber(particlesSettings.lifetimeSec, 1.6),
    particlesSpeed: toNumber(particlesSettings.speed, 1),
    particlesReactivity: toNumber(particlesSettings.reactivity, 0.1),
    particlesAudioTravelBoost: toNumber(particlesSettings.audioTravelBoost, 1),
    particlesAudioMotionMode: toStringValue(particlesSettings.audioMotionMode, 'both'),
    particlesSmoothing: toNumber(particlesSettings.smoothing, 0.65),
    particlesSpawnMode: toStringValue(particlesSettings.spawnMode, 'always'),
    particlesSpawnTrigger: toStringValue(particlesSettings.spawnTrigger, 'both'),
    particlesSpawnThreshold: toNumber(particlesSettings.spawnThreshold, 0.15),
    particlesVariant: toStringValue(particlesSettings.variant, 'classic'),
    particlesSpawnArea: toStringValue(particlesSettings.spawnArea, 'centerRing'),
    particlesSizeJitter: toNumber(particlesSettings.sizeJitter, 0),
    particlesDrift: toNumber(particlesSettings.drift, 0),
    particlesSwirl: toNumber(particlesSettings.swirl, 0),
    particlesStyle: toStringValue(particlesSettings.style, 'dot'),
    particlesSize: toNumber(particlesSettings.size, 2),
    particlesOpacity: toNumber(particlesSettings.opacity, 0.35),
    particlesColor: normalizeColor(particlesSettings.color, '#ffffff'),
    particlesReactColor: normalizeColor(particlesSettings.reactColor, '#ffffff'),
    particlesReactStrength: toNumber(particlesSettings.reactStrength, 0.65),
  }
}

export function buildParticlesTemplatePatch(
  template: Record<string, unknown>,
  draft: ParticleSettingsState,
): Record<string, unknown> {
  const currentParticlesSettings = toRecord(template.particlesSettings)

  return {
    particlesSettings: {
      ...currentParticlesSettings,
      enabled: draft.particlesEnabled,
      maxCount: draft.particlesMaxCount,
      spawnRate: draft.particlesSpawnRate,
      lifetimeSec: draft.particlesLifetimeSec,
      speed: draft.particlesSpeed,
      reactivity: draft.particlesReactivity,
      audioMotionMode: draft.particlesAudioMotionMode,
      audioTravelBoost: draft.particlesAudioTravelBoost,
      smoothing: draft.particlesSmoothing,
      spawnMode: draft.particlesSpawnMode,
      spawnTrigger: draft.particlesSpawnTrigger,
      spawnThreshold: draft.particlesSpawnThreshold,
      variant: draft.particlesVariant,
      spawnArea: draft.particlesSpawnArea,
      sizeJitter: draft.particlesSizeJitter,
      drift: draft.particlesDrift,
      swirl: draft.particlesSwirl,
      style: draft.particlesStyle,
      size: draft.particlesSize,
      opacity: draft.particlesOpacity,
      color: draft.particlesColor,
      reactColor: draft.particlesReactColor,
      reactStrength: draft.particlesReactStrength,
    },
  }
}
