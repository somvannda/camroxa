import { buildWebGpuSpectrumInstances, type SpectrumLayerPreview } from '@/features/video/preview/spectrumAdapter'

describe('spectrumAdapter straight bars premium path', () => {
  it('emits dedicated straight-bars instances instead of the generic variant', () => {
    const layer: SpectrumLayerPreview = {
      id: 'straight-bars',
      styleKey: 'straight-bars',
      colorMode: 'gradient',
      gradientDirection: 'left-to-right',
      radiusOffset: 0,
      thickness: 76,
      barWidth: 4.6,
      solidBand: false,
      opacity: 0.97,
      glow: 14,
      blur: 2,
      curved: false,
      mirrored: false,
      fillCircle: false,
      gravity: 'bottom',
      blendMode: 'normal',
      colors: ['#ff71cf', '#f5eeff', '#7d85ff', '#5de3ff'],
    }

    const instances = buildWebGpuSpectrumInstances(
      960,
      540,
      0,
      layer,
      [0.15, 0.32, 0.58, 0.9],
      0.7,
      1,
    )

    expect(instances.length).toBeGreaterThan(0)
    expect(instances.every((instance) => instance.variant === 6)).toBe(true)
    expect(instances.some((instance) => instance.blendMode === 'screen')).toBe(true)
    expect(instances.some((instance) => instance.blendMode === 'normal')).toBe(true)
  })

  it('keeps spike height as a strong geometry control with enough headroom for tall bars', () => {
    const createLayer = (thickness: number): SpectrumLayerPreview => ({
      id: `straight-bars-${thickness}`,
      styleKey: 'straight-bars',
      colorMode: 'gradient',
      gradientDirection: 'left-to-right',
      radiusOffset: 0,
      thickness,
      barWidth: 4.6,
      solidBand: false,
      opacity: 0.97,
      glow: 0,
      blur: 0,
      curved: false,
      mirrored: false,
      fillCircle: false,
      gravity: 'bottom',
      blendMode: 'normal',
      colors: ['#ff71cf', '#f5eeff', '#7d85ff', '#5de3ff'],
    })

    const values = [0.2, 0.46, 0.72, 0.94]
    const shortInstances = buildWebGpuSpectrumInstances(960, 540, 0, createLayer(60), values, 0.72, 1)
    const tallInstances = buildWebGpuSpectrumInstances(960, 540, 0, createLayer(180), values, 0.72, 1)
    const shortMaxLength = Math.max(...shortInstances.map((instance) => instance.length))
    const tallMaxLength = Math.max(...tallInstances.map((instance) => instance.length))

    expect(tallMaxLength).toBeGreaterThan(shortMaxLength * 2.2)
  })
})

describe('spectrumAdapter flying glow wing density', () => {
  it('emits a wide wing-family variant so the silhouette can read as near-solid', () => {
    const layer: SpectrumLayerPreview = {
      id: 'flying-glow',
      styleKey: 'flying-glow',
      colorMode: 'gradient',
      gradientDirection: 'left-to-right',
      radiusOffset: 0,
      thickness: 86,
      barWidth: 7,
      solidBand: false,
      opacity: 0.96,
      glow: 56,
      blur: 12,
      curved: true,
      mirrored: true,
      fillCircle: false,
      gravity: 'bottom',
      blendMode: 'screen',
      colors: ['#55e8ff', '#f8fbff', '#9d84ff'],
    }

    const instances = buildWebGpuSpectrumInstances(
      960,
      540,
      240,
      layer,
      [0.18, 0.36, 0.58, 0.84],
      0.8,
      1,
    )

    expect(instances.length).toBeGreaterThan(0)
    expect(instances.every((instance) => instance.variant === 4)).toBe(true)
    expect(instances.some((instance) => instance.halfWidth >= 5)).toBe(true)
    expect(instances.some((instance) => instance.blendMode === 'opaque')).toBe(true)
    expect(instances.length).toBeGreaterThan(120)
  })

  it('keeps an opaque flying glow foundation ring nearly uniform before the flare reacts', () => {
    const layer: SpectrumLayerPreview = {
      id: 'flying-glow-foundation',
      styleKey: 'flying-glow',
      colorMode: 'gradient',
      gradientDirection: 'left-to-right',
      radiusOffset: 0,
      thickness: 86,
      barWidth: 7,
      solidBand: true,
      opacity: 0.96,
      glow: 0,
      blur: 0,
      curved: true,
      mirrored: true,
      fillCircle: false,
      gravity: 'bottom',
      blendMode: 'normal',
      colors: ['#55e8ff', '#f8fbff', '#9d84ff'],
    }

    const instances = buildWebGpuSpectrumInstances(
      960,
      540,
      240,
      layer,
      [0.1, 0.92, 0.18, 0.88, 0.14, 0.9, 0.2],
      0.2,
      1,
      0.04,
    ).filter((instance) => instance.blendMode === 'opaque')

    const lengths = instances.map((instance) => instance.length)
    const spread = Math.max(...lengths) - Math.min(...lengths)

    expect(instances.length).toBeGreaterThan(0)
    expect(spread).toBeLessThan(6)
  })

  it('uses gravity to shift the strongest flying glow lift toward the opposite side of the circle', () => {
    const createLayer = (gravity: 'bottom' | 'top'): SpectrumLayerPreview => ({
      id: `flying-glow-gravity-${gravity}`,
      styleKey: 'flying-glow',
      colorMode: 'gradient',
      gradientDirection: 'left-to-right',
      radiusOffset: 0,
      thickness: 86,
      barWidth: 7,
      solidBand: true,
      opacity: 0.96,
      glow: 0,
      blur: 0,
      curved: true,
      mirrored: true,
      fillCircle: false,
      gravity,
      blendMode: 'normal',
      colors: ['#55e8ff', '#f8fbff', '#9d84ff'],
    })

    const values = [0.12, 0.44, 0.82, 0.36, 0.22, 0.68, 0.28]
    const bottomInstances = buildWebGpuSpectrumInstances(960, 540, 240, createLayer('bottom'), values, 0.72, 1, 0.78)
      .filter((instance) => instance.blendMode === 'opaque')
      .sort((left, right) => right.length - left.length)
      .slice(0, 24)
    const topInstances = buildWebGpuSpectrumInstances(960, 540, 240, createLayer('top'), values, 0.72, 1, 0.78)
      .filter((instance) => instance.blendMode === 'opaque')
      .sort((left, right) => right.length - left.length)
      .slice(0, 24)

    const bottomAverageY =
      bottomInstances.reduce((sum, instance) => sum + instance.baseY, 0) / bottomInstances.length
    const topAverageY =
      topInstances.reduce((sum, instance) => sum + instance.baseY, 0) / topInstances.length

    expect(bottomInstances.length).toBeGreaterThan(0)
    expect(topInstances.length).toBeGreaterThan(0)
    expect(bottomAverageY).toBeLessThan(540)
    expect(topAverageY).toBeGreaterThan(540)
  })

  it('keeps the gravity source side reacting too, so bottom-to-top travel does not leave the bottom dead', () => {
    const layer: SpectrumLayerPreview = {
      id: 'flying-glow-bottom-travel',
      styleKey: 'flying-glow',
      colorMode: 'gradient',
      gradientDirection: 'left-to-right',
      radiusOffset: 0,
      thickness: 86,
      barWidth: 7,
      solidBand: true,
      opacity: 0.96,
      glow: 0,
      blur: 0,
      curved: true,
      mirrored: true,
      fillCircle: false,
      gravity: 'bottom',
      blendMode: 'normal',
      colors: ['#55e8ff', '#f8fbff', '#9d84ff'],
    }

    const values = [0.12, 0.44, 0.82, 0.36, 0.22, 0.68, 0.28]
    const calmInstances = buildWebGpuSpectrumInstances(960, 540, 240, layer, values, 0.12, 1, 0.12).filter(
      (instance) => instance.blendMode === 'opaque',
    )
    const activeInstances = buildWebGpuSpectrumInstances(960, 540, 240, layer, values, 0.72, 1, 0.78).filter(
      (instance) => instance.blendMode === 'opaque',
    )

    const calmBottom = calmInstances
      .filter((instance) => instance.baseY > 540)
      .reduce((sum, instance) => sum + instance.length, 0)
    const activeBottom = activeInstances
      .filter((instance) => instance.baseY > 540)
      .reduce((sum, instance) => sum + instance.length, 0)

    expect(activeBottom).toBeGreaterThan(calmBottom * 1.18)
  })

  it('keeps the resting curved ring close to uniform before kick flare extends the wing', () => {
    const layer: SpectrumLayerPreview = {
      id: 'flying-glow-rest',
      styleKey: 'flying-glow',
      colorMode: 'gradient',
      gradientDirection: 'left-to-right',
      radiusOffset: 0,
      thickness: 86,
      barWidth: 7,
      solidBand: false,
      opacity: 0.96,
      glow: 0,
      blur: 0,
      curved: true,
      mirrored: true,
      fillCircle: false,
      gravity: 'bottom',
      blendMode: 'normal',
      colors: ['#55e8ff', '#f8fbff', '#9d84ff'],
    }

    const instances = buildWebGpuSpectrumInstances(
      960,
      540,
      240,
      layer,
      Array.from({ length: 12 }, () => 0),
      0,
      1,
    )

    const foundationInstances = instances.filter((instance) => instance.blendMode === 'opaque')
    const lengths = foundationInstances.map((instance) => instance.length)
    const minLength = Math.min(...lengths)
    const maxLength = Math.max(...lengths)

    expect(foundationInstances.length).toBeGreaterThan(0)
    expect(maxLength - minLength).toBeLessThan(0.001)
  })

  it('maps flying glow gradients from ring position so the glow body can show the full palette', () => {
    const layer: SpectrumLayerPreview = {
      id: 'flying-glow-gradient-body',
      styleKey: 'flying-glow',
      colorMode: 'gradient',
      gradientDirection: 'top-to-bottom',
      radiusOffset: 0,
      thickness: 86,
      barWidth: 7,
      solidBand: false,
      opacity: 0.96,
      glow: 32,
      blur: 6,
      curved: true,
      mirrored: true,
      fillCircle: false,
      gravity: 'bottom',
      blendMode: 'screen',
      colors: ['#ff2a6d', '#f8fbff', '#22d3ee', '#7c3aed'],
    }

    const wingInstances = buildWebGpuSpectrumInstances(
      960,
      540,
      240,
      layer,
      Array.from({ length: 12 }, () => 0.24),
      0.48,
      1,
      0.7,
    ).filter((instance) => instance.blendMode !== 'opaque')

    const gradientValues = wingInstances.map((instance) => instance.gradientU)
    const gradientSpread = Math.max(...gradientValues) - Math.min(...gradientValues)

    expect(wingInstances.length).toBeGreaterThan(0)
    expect(gradientSpread).toBeGreaterThan(0.85)
  })

  it('gives flying glow clear visible travel once the ring is reacting to music', () => {
    const layer: SpectrumLayerPreview = {
      id: 'flying-glow-active',
      styleKey: 'flying-glow',
      colorMode: 'gradient',
      gradientDirection: 'left-to-right',
      radiusOffset: 0,
      thickness: 86,
      barWidth: 7,
      solidBand: false,
      opacity: 0.96,
      glow: 32,
      blur: 6,
      curved: true,
      mirrored: true,
      fillCircle: false,
      gravity: 'bottom',
      blendMode: 'screen',
      colors: ['#55e8ff', '#f8fbff', '#9d84ff'],
    }

    const calmInstances = buildWebGpuSpectrumInstances(
      960,
      540,
      240,
      layer,
      [0.08, 0.12, 0.16, 0.11, 0.09],
      0.12,
      1,
      0.08,
    )
    const activeInstances = buildWebGpuSpectrumInstances(
      960,
      540,
      240,
      layer,
      [0.16, 0.34, 0.62, 0.86, 0.58],
      0.66,
      1,
      0.72,
    )

    const calmMax = Math.max(...calmInstances.map((instance) => instance.length))
    const activeMax = Math.max(...activeInstances.map((instance) => instance.length))

    expect(activeMax).toBeGreaterThan(calmMax * 1.6)
  })

  it('lets flying glow flare follow a fast style-motion drive instead of only the slower shared reactive energy', () => {
    const layer: SpectrumLayerPreview = {
      id: 'flying-glow-motion-drive',
      styleKey: 'flying-glow',
      colorMode: 'gradient',
      gradientDirection: 'left-to-right',
      radiusOffset: 0,
      thickness: 86,
      barWidth: 7,
      solidBand: false,
      opacity: 0.96,
      glow: 32,
      blur: 6,
      curved: true,
      mirrored: true,
      fillCircle: false,
      gravity: 'bottom',
      blendMode: 'screen',
      colors: ['#55e8ff', '#f8fbff', '#9d84ff'],
    }

    const values = [0.12, 0.24, 0.4, 0.68, 0.42]
    const lowDriveInstances = buildWebGpuSpectrumInstances(960, 540, 240, layer, values, 0.46, 1, 0.12)
    const highDriveInstances = buildWebGpuSpectrumInstances(960, 540, 240, layer, values, 0.46, 1, 0.78)
    const lowDriveMax = Math.max(...lowDriveInstances.map((instance) => instance.length))
    const highDriveMax = Math.max(...highDriveInstances.map((instance) => instance.length))

    expect(highDriveMax).toBeGreaterThan(lowDriveMax * 1.3)
  })

  it('keeps medium flying glow drive closer to ring-first while reserving the largest flare for stronger beats', () => {
    const layer: SpectrumLayerPreview = {
      id: 'flying-glow-beat-separation',
      styleKey: 'flying-glow',
      colorMode: 'gradient',
      gradientDirection: 'left-to-right',
      radiusOffset: 0,
      thickness: 86,
      barWidth: 7,
      solidBand: false,
      opacity: 0.96,
      glow: 32,
      blur: 6,
      curved: true,
      mirrored: true,
      fillCircle: false,
      gravity: 'bottom',
      blendMode: 'screen',
      colors: ['#55e8ff', '#f8fbff', '#9d84ff'],
    }

    const values = [0.12, 0.24, 0.4, 0.68, 0.42]
    const mediumDriveInstances = buildWebGpuSpectrumInstances(960, 540, 240, layer, values, 0.48, 1, 0.24)
    const hardDriveInstances = buildWebGpuSpectrumInstances(960, 540, 240, layer, values, 0.48, 1, 0.86)
    const mediumDriveMax = Math.max(...mediumDriveInstances.map((instance) => instance.length))
    const hardDriveMax = Math.max(...hardDriveInstances.map((instance) => instance.length))

    expect(hardDriveMax).toBeGreaterThan(mediumDriveMax * 1.45)
  })

  it('keeps low-drive flying glow closer to a rounder ring while shoulder flare appears mainly on strong beats', () => {
    const layer: SpectrumLayerPreview = {
      id: 'flying-glow-ring-vs-wing',
      styleKey: 'flying-glow',
      colorMode: 'gradient',
      gradientDirection: 'left-to-right',
      radiusOffset: 0,
      thickness: 86,
      barWidth: 7,
      solidBand: false,
      opacity: 0.96,
      glow: 32,
      blur: 6,
      curved: true,
      mirrored: true,
      fillCircle: false,
      gravity: 'bottom',
      blendMode: 'screen',
      colors: ['#55e8ff', '#f8fbff', '#9d84ff'],
    }

    const values = [0.16, 0.48, 0.28, 0.22, 0.26, 0.5, 0.18]
    const lowDriveInstances = buildWebGpuSpectrumInstances(960, 540, 240, layer, values, 0.5, 1, 0.08)
    const highDriveInstances = buildWebGpuSpectrumInstances(960, 540, 240, layer, values, 0.5, 1, 0.9)
    const lowLengths = lowDriveInstances.map((instance) => instance.length)
    const highLengths = highDriveInstances.map((instance) => instance.length)
    const lowSpread = Math.max(...lowLengths) - Math.min(...lowLengths)
    const highSpread = Math.max(...highLengths) - Math.min(...highLengths)

    expect(highSpread).toBeGreaterThan(lowSpread * 1.35)
  })

  it('smooths flying glow geometry so alternating bars read as a more continuous wing', () => {
    const layer: SpectrumLayerPreview = {
      id: 'flying-glow-smoothing',
      styleKey: 'flying-glow',
      colorMode: 'gradient',
      gradientDirection: 'left-to-right',
      radiusOffset: 0,
      thickness: 86,
      barWidth: 7,
      solidBand: false,
      opacity: 0.96,
      glow: 24,
      blur: 6,
      curved: true,
      mirrored: true,
      fillCircle: false,
      gravity: 'bottom',
      blendMode: 'screen',
      colors: ['#55e8ff', '#f8fbff', '#9d84ff'],
    }

    const values = [0.12, 0.9, 0.16, 0.88, 0.14, 0.92, 0.18]
    const instances = buildWebGpuSpectrumInstances(960, 540, 240, layer, values, 0.56, 1, 0.74)
    let maxAdjacentDelta = 0
    for (let index = 1; index < instances.length; index += 1) {
      maxAdjacentDelta = Math.max(maxAdjacentDelta, Math.abs(instances[index].length - instances[index - 1].length))
    }

    expect(maxAdjacentDelta).toBeLessThan(38)
  })
})
