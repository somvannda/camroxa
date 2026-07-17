import { buildSpectrumLayers } from '@/features/video/domains/spectrum/spectrumLayerModel'

describe('buildSpectrumLayers color resolution', () => {
  it('keeps valid live color-engine values instead of collapsing invalid stops to black', () => {
    const [layer] = buildSpectrumLayers({
      style: 'straight-bars',
      layers: [
        {
          color: {
            mode: 'gradient',
            gradientDirection: 'left-to-right',
            gradientColors: ['rgba(255, 0, 128, 1)', '#00ffff', { color: '#7c3aed' }],
          },
        },
      ],
    })

    expect(layer?.colors).toEqual(['rgba(255, 0, 128, 1)', '#00ffff', '#7c3aed'])
  })

  it('falls back to a safe two-stop gradient when the stored gradient payload is malformed', () => {
    const [layer] = buildSpectrumLayers({
      style: 'straight-bars',
      layers: [
        {
          color: {
            mode: 'gradient',
            gradientColors: [{ value: 'not-a-color' }, null],
          },
        },
      ],
    })

    expect(layer?.colors).toEqual(['#8b5cf6', '#22d3ee'])
  })

  it('accepts legacy root-level color fields when nested color records are missing', () => {
    const [layer] = buildSpectrumLayers({
      style: 'straight-bars',
      layers: [
        {
          colorMode: 'gradient',
          gradientDirection: 'left-to-right',
          gradientColors: ['#ff0000', '#0000ff'],
        },
      ],
    })

    expect(layer?.colorMode).toBe('gradient')
    expect(layer?.colors).toEqual(['#ff0000', '#0000ff'])
  })

  it('preserves solid band geometry and wider bar widths from the layer record', () => {
    const [layer] = buildSpectrumLayers({
      style: 'straight-bars',
      layers: [
        {
          barWidth: 72,
          solidBand: true,
        },
      ],
    })

    expect(layer?.barWidth).toBe(72)
    expect(layer?.solidBand).toBe(true)
  })
})
