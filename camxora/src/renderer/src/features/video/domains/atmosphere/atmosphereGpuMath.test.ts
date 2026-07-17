import { buildWebGpuAtmosphereSettings } from '@/features/video/domains/atmosphere/atmosphereGpuMath'

describe('buildWebGpuAtmosphereSettings', () => {
  it('returns null when both smoke and vignette are effectively disabled', () => {
    const result = buildWebGpuAtmosphereSettings(
      {
        smokeEnabled: false,
        smokeOpacity: 0,
        smokeStrength: 0,
        vignetteEnabled: false,
        vignetteOpacity: 0,
      } as never,
      2,
    )

    expect(result).toBeNull()
  })

  it('builds clamped GPU atmosphere settings when smoke or vignette is visible', () => {
    const result = buildWebGpuAtmosphereSettings(
      {
        smokeEnabled: true,
        smokeOpacity: 1.2,
        smokeStrength: 1.4,
        smokeBlur: 1.1,
        smokeNoise: 1.2,
        smokeSpeed: 0.1,
        smokeColor: '#336699',
        vignetteEnabled: true,
        vignetteStrength: 1.3,
        vignetteFeather: 0.01,
        vignetteOpacity: 1.1,
        vignetteColor: '#112233',
      } as never,
      3,
    )

    expect(result).toEqual(
      expect.objectContaining({
        timeSec: 3,
        smokeEnabled: true,
        smokeOpacity: 1,
        smokeStrength: 1,
        smokeBlur: 1,
        smokeNoise: 1,
        smokeSpeed: 0.2,
        vignetteEnabled: true,
        vignetteStrength: 1,
        vignetteFeather: 0.05,
        vignetteOpacity: 1,
      }),
    )
  })
})
