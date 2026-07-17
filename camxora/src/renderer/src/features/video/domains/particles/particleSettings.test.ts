import {
  buildParticleMotionPresetPatch,
  PARTICLE_MOTION_PRESET_FIELD_KEYS,
  PARTICLE_MOTION_PRESETS,
} from '@/features/video/domains/particles/particleSettings'

describe('buildParticleMotionPresetPatch', () => {
  it('exposes the curated particle preset set', () => {
    expect(PARTICLE_MOTION_PRESETS.map((preset) => preset.value)).toEqual([
      'embers',
      'dust_field',
      'dreamy_bokeh',
      'soap_orbit',
      'energy_sparks',
      'flash_sparks',
    ])
  })

  it('builds a punchy reactive spark recipe for energy_sparks', () => {
    expect(buildParticleMotionPresetPatch('energy_sparks')).toEqual(
      expect.objectContaining({
        particlesEnabled: true,
        particlesSpawnMode: 'reactiveOnly',
        particlesSpawnTrigger: 'kick',
        particlesStyle: 'spark',
        particlesSpeed: 5.4,
      }),
    )
  })

  it('builds a slow ambient recipe for dust_field', () => {
    expect(buildParticleMotionPresetPatch('dust_field')).toEqual(
      expect.objectContaining({
        particlesEnabled: true,
        particlesSpawnMode: 'always',
        particlesVariant: 'dust',
        particlesSpawnArea: 'full',
        particlesLifetimeSec: 5.2,
      }),
    )
  })

  it('builds an instant flash-and-fade recipe for flash_sparks', () => {
    expect(buildParticleMotionPresetPatch('flash_sparks')).toEqual(
      expect.objectContaining({
        particlesEnabled: true,
        particlesSpawnMode: 'reactiveOnly',
        particlesSpawnTrigger: 'kick',
        particlesStyle: 'spark',
        particlesLifetimeSec: 0.38,
        particlesReactStrength: 1,
      }),
    )
  })

  it('defines every preset as a full particle recipe', () => {
    const embers = buildParticleMotionPresetPatch('embers')
    expect(PARTICLE_MOTION_PRESET_FIELD_KEYS.every((fieldKey) => fieldKey in embers)).toBe(true)
  })
})
