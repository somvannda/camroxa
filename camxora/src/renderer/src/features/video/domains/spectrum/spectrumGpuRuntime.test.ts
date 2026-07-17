import { buildSpectrumGpuInstances } from '@/features/video/domains/spectrum/spectrumGpuRuntime'

const mockBuildWebGpuSpectrumInstances = vi.fn()
const mockBuildWebGpuSpectrumGradientAtlas = vi.fn()
const mockNormalizeSpectrumStyleKey = vi.fn()

vi.mock('@/features/video/domains/spectrum/spectrumLayerModel', () => ({
  normalizeSpectrumStyleKey: (...args: unknown[]) => mockNormalizeSpectrumStyleKey(...args),
}))

vi.mock('@/features/video/domains/spectrum/spectrumRendererAdapter', () => ({
  buildWebGpuSpectrumGradientAtlas: (...args: unknown[]) =>
    mockBuildWebGpuSpectrumGradientAtlas(...args),
  buildWebGpuSpectrumInstances: (...args: unknown[]) => mockBuildWebGpuSpectrumInstances(...args),
}))

describe('buildSpectrumGpuInstances', () => {
  beforeEach(() => {
    mockBuildWebGpuSpectrumInstances.mockReset()
    mockBuildWebGpuSpectrumGradientAtlas.mockReset()
    mockNormalizeSpectrumStyleKey.mockReset()
  })

  it('reuses the prebuilt per-frame audio signal before falling back to per-layer spectrum rebuilding', () => {
    const buildLayerSpectrumValues = vi.fn().mockReturnValue(null)
    const buildSyntheticSpectrumValues = vi.fn()

    mockNormalizeSpectrumStyleKey.mockImplementation((styleKey: string) => styleKey)
    mockBuildWebGpuSpectrumGradientAtlas.mockReturnValue({
      width: 256,
      height: 2,
      rgba: new Uint8Array(256 * 2 * 4),
    })
    mockBuildWebGpuSpectrumInstances
      .mockReturnValueOnce([{ id: 'instance-a' }])
      .mockReturnValueOnce([{ id: 'instance-b' }])

    const result = buildSpectrumGpuInstances({
      analysedFrame: { styleMotionDrive: 0.45 } as never,
      audioSignal: {
        renderValues: [0.4, 0.5, 0.6],
        mirroredRenderValues: [0.1, 0.2, 0.3],
      } as never,
      buildLayerSpectrumValues,
      buildSyntheticSpectrumValues,
      centerX: 320,
      centerY: 180,
      hasBoundAudio: false,
      motionState: {
        flyingGlowPulseDrive: 0.9,
      },
      reactiveEnergy: 0.7,
      scale: 2,
      spectrumAttachment: {
        attachedToLogo: true,
        baseRadius: 100,
        centerOffsetX: 0,
        centerOffsetY: 0,
      },
      spectrumBarCount: 3,
      spectrumLayers: [
        { styleKey: 'flying-glow', mirrored: true, radiusOffset: 20 },
        { styleKey: 'straight-bars', mirrored: false, radiusOffset: 40 },
      ] as never,
      templateDraft: {
        audioInputGain: 1.1,
        audioBarHeight: 1.8,
        audioMotionSmoothing: 0.7,
        spectrumEnabled: true,
      } as never,
      timeSec: 2,
      useWebGpuSpectrum: true,
    })

    expect(buildLayerSpectrumValues).not.toHaveBeenCalled()
    expect(buildSyntheticSpectrumValues).not.toHaveBeenCalled()
    expect(mockBuildWebGpuSpectrumGradientAtlas).toHaveBeenCalledWith([
      { styleKey: 'flying-glow', mirrored: true, radiusOffset: 20 },
      { styleKey: 'straight-bars', mirrored: false, radiusOffset: 40 },
    ])
    expect(mockBuildWebGpuSpectrumInstances).toHaveBeenCalledTimes(2)
    const [firstCall, secondCall] = mockBuildWebGpuSpectrumInstances.mock.calls
    expect(firstCall).toBeDefined()
    expect(secondCall).toBeDefined()
    expect(firstCall?.[0]).toBe(320)
    expect(firstCall?.[1]).toBe(180)
    expect(firstCall?.[3]).toEqual(expect.objectContaining({ styleKey: 'flying-glow' }))
    expect(firstCall?.[4]).toEqual([0.1, 0.2, 0.3])
    expect(firstCall?.[5]).toBe(0.7)
    expect(firstCall?.[6]).toBe(2)
    expect(firstCall?.[7]).toBe(0.9)
    expect(firstCall?.[8]).toEqual(expect.objectContaining({ gradientV: 0.25, heightScale: 1.8 }))
    expect(secondCall?.[0]).toBe(320)
    expect(secondCall?.[1]).toBe(180)
    expect(secondCall?.[3]).toEqual(expect.objectContaining({ styleKey: 'straight-bars' }))
    expect(secondCall?.[4]).toEqual([0.4, 0.5, 0.6])
    expect(secondCall?.[5]).toBe(0.7)
    expect(secondCall?.[6]).toBe(2)
    expect(secondCall?.[7]).toBe(0.45)
    expect(secondCall?.[8]).toEqual(expect.objectContaining({ gradientV: 0.75, heightScale: 1.8 }))
    expect(Number(firstCall?.[2] ?? 0)).toBeGreaterThan(0)
    expect(Number(secondCall?.[2] ?? 0)).toBeGreaterThan(Number(firstCall?.[2] ?? 0))
    expect(result.gradientAtlas).toEqual({
      width: 256,
      height: 2,
      rgba: expect.any(Uint8Array),
    })
    expect(result.gpuInstances).toEqual([{ id: 'instance-a' }, { id: 'instance-b' }])
    expect(result.instancesMs).toEqual(expect.any(Number))
  })

  it('returns no instances when spectrum rendering is disabled for the frame', () => {
    const result = buildSpectrumGpuInstances({
      analysedFrame: null,
      audioSignal: null,
      buildLayerSpectrumValues: vi.fn(),
      buildSyntheticSpectrumValues: vi.fn(),
      centerX: 0,
      centerY: 0,
      hasBoundAudio: true,
      motionState: {
        flyingGlowPulseDrive: 0,
      },
      reactiveEnergy: 0,
      scale: 1,
      spectrumAttachment: null,
      spectrumBarCount: 64,
      spectrumLayers: [{ styleKey: 'straight-bars', mirrored: true, radiusOffset: 0 }] as never,
      templateDraft: {
        spectrumEnabled: true,
      } as never,
      timeSec: 0,
      useWebGpuSpectrum: false,
    })

    expect(mockBuildWebGpuSpectrumInstances).not.toHaveBeenCalled()
    expect(result).toEqual({
      gradientAtlas: null,
      gpuInstances: [],
      instancesMs: 0,
    })
  })
})
