import { buildAtmosphereGpuSettings } from '@/features/video/domains/atmosphere/atmosphereGpuRuntime'

const mockBuildWebGpuAtmosphereSettings = vi.fn()

vi.mock('@/features/video/domains/atmosphere/atmosphereGpuMath', () => ({
  buildWebGpuAtmosphereSettings: (...args: unknown[]) => mockBuildWebGpuAtmosphereSettings(...args),
}))

describe('buildAtmosphereGpuSettings', () => {
  beforeEach(() => {
    mockBuildWebGpuAtmosphereSettings.mockReset()
  })

  it('builds atmosphere settings through the atmosphere domain runtime seam', () => {
    mockBuildWebGpuAtmosphereSettings.mockReturnValue({ haze: 0.2 })

    const result = buildAtmosphereGpuSettings({
      atmosphereEnabled: true,
      templateDraft: { smokeEnabled: true } as never,
      timeSec: 2,
    })

    expect(mockBuildWebGpuAtmosphereSettings).toHaveBeenCalledWith(
      expect.objectContaining({ smokeEnabled: true }),
      2,
    )
    expect(result).toEqual({ haze: 0.2 })
  })

  it('returns null when atmosphere is disabled for the frame', () => {
    const result = buildAtmosphereGpuSettings({
      atmosphereEnabled: false,
      templateDraft: {} as never,
      timeSec: 0,
    })

    expect(mockBuildWebGpuAtmosphereSettings).not.toHaveBeenCalled()
    expect(result).toBeNull()
  })
})
