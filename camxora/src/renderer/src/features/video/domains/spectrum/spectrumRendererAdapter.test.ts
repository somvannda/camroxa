import {
  buildWebGpuSpectrumGradientAtlas,
  buildWebGpuSpectrumInstances,
} from '@/features/video/domains/spectrum/spectrumRendererAdapter'
import type { SpectrumLayerPreview } from '@/features/video/domains/spectrum/spectrumLayerModel'

const BASE_LAYER: SpectrumLayerPreview = {
  id: 'layer-1',
  styleKey: 'straight-bars',
  colorMode: 'gradient',
  gradientDirection: 'left-to-right',
  radiusOffset: 0,
  thickness: 64,
  barWidth: 4,
  solidBand: false,
  opacity: 1,
  glow: 0,
  blur: 0,
  curved: false,
  mirrored: false,
  fillCircle: false,
  gravity: 'bottom',
  blendMode: 'normal',
  colors: ['#ff00ff', '#00ffff'],
}

describe('buildWebGpuSpectrumGradientAtlas', () => {
  it('produces non-black atlas pixels for non-black spectrum colors', () => {
    const atlas = buildWebGpuSpectrumGradientAtlas([BASE_LAYER])

    expect(atlas.width).toBe(256)
    expect(atlas.height).toBe(1)
    expect(Array.from(atlas.rgba.slice(0, 4))).toEqual([255, 0, 255, 255])
    expect(Array.from(atlas.rgba.slice(0, 16)).some((value, index) => index % 4 !== 3 && value > 0)).toBe(true)
  })
})

describe('buildWebGpuSpectrumInstances', () => {
  it('keeps a non-black packed fallback RGB for gradient-backed instances', () => {
    const [instance] = buildWebGpuSpectrumInstances(
      960,
      540,
      0,
      BASE_LAYER,
      [0.2, 0.5, 0.8],
      0.6,
      1,
    )

    expect(instance).toEqual(
      expect.objectContaining({
        red: 1,
        green: 0,
        blue: 1,
      }),
    )
  })

  it('lets heightScale directly increase generated bar length', () => {
    const [baseInstance] = buildWebGpuSpectrumInstances(
      960,
      540,
      0,
      BASE_LAYER,
      [0.5],
      0.4,
      1,
      0.4,
      { heightScale: 1 },
    )
    const [tallInstance] = buildWebGpuSpectrumInstances(
      960,
      540,
      0,
      BASE_LAYER,
      [0.5],
      0.4,
      1,
      0.4,
      { heightScale: 2 },
    )

    expect(tallInstance.length).toBeGreaterThan(baseInstance.length * 1.4)
  })

  it('can widen bars into a continuous solid band', () => {
    const [segmentedInstance] = buildWebGpuSpectrumInstances(
      960,
      540,
      0,
      BASE_LAYER,
      [0.5, 0.55, 0.6, 0.65, 0.7],
      0.4,
      1,
      0.4,
    )
    const [solidBandInstance] = buildWebGpuSpectrumInstances(
      960,
      540,
      0,
      { ...BASE_LAYER, solidBand: true, barWidth: 2 },
      [0.5, 0.55, 0.6, 0.65, 0.7],
      0.4,
      1,
      0.4,
    )

    expect(solidBandInstance.halfWidth).toBeGreaterThan(segmentedInstance.halfWidth * 2)
  })

  it('smooths flying glow solid-band geometry so the wing reads less segmented', () => {
    const flyingGlowLayer: SpectrumLayerPreview = {
      ...BASE_LAYER,
      id: 'flying-glow-solid',
      styleKey: 'flying-glow',
      curved: true,
      mirrored: true,
      glow: 28,
      blur: 8,
      barWidth: 7,
      thickness: 86,
      blendMode: 'screen',
    }
    const values = [0.12, 0.92, 0.18, 0.88, 0.16, 0.9, 0.14]
    const segmented = buildWebGpuSpectrumInstances(960, 540, 240, flyingGlowLayer, values, 0.58, 1, 0.78)
    const solidBand = buildWebGpuSpectrumInstances(
      960,
      540,
      240,
      { ...flyingGlowLayer, solidBand: true },
      values,
      0.58,
      1,
      0.78,
    )

    const segmentedSpread = Math.max(...segmented.map((instance) => instance.length)) - Math.min(...segmented.map((instance) => instance.length))
    const solidSpread = Math.max(...solidBand.map((instance) => instance.length)) - Math.min(...solidBand.map((instance) => instance.length))
    const segmentedAverageHalfWidth =
      segmented.reduce((sum, instance) => sum + instance.halfWidth, 0) / segmented.length
    const solidAverageHalfWidth =
      solidBand.reduce((sum, instance) => sum + instance.halfWidth, 0) / solidBand.length

    expect(solidSpread).toBeLessThanOrEqual(segmentedSpread)
    expect(solidAverageHalfWidth + 0.0001).toBeGreaterThanOrEqual(segmentedAverageHalfWidth)
  })
})
