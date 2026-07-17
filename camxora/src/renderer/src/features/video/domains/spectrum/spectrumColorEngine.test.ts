import {
  applySpectrumLayerColorPatch,
  buildSpectrumGradientPresetValue,
  extractSpectrumLayerColorModel,
  normalizeSpectrumGradientColors,
} from '@/features/video/domains/spectrum/spectrumColorEngine'

describe('spectrumColorEngine', () => {
  it('extracts a normalized gradient color model from nested layer color data', () => {
    const colorModel = extractSpectrumLayerColorModel(
      {
        color: {
          mode: 'gradient',
          gradientDirection: 'diagonal',
          gradientColors: ['rgba(255, 0, 128, 1)', '#00ffff'],
        },
      },
      '#8b5cf6',
    )

    expect(colorModel).toEqual({
      mode: 'gradient',
      solidColor: '#8b5cf6',
      gradientDirection: 'diagonal',
      gradientColors: ['rgba(255, 0, 128, 1)', '#00ffff'],
      colors: ['rgba(255, 0, 128, 1)', '#00ffff'],
    })
  })

  it('synchronizes nested and legacy layer fields when applying a color patch', () => {
    const nextLayer = applySpectrumLayerColorPatch(
      {
        color: {
          mode: 'solid',
          solidColor: '#ffffff',
        },
      },
      {
        mode: 'gradient',
        gradientDirection: 'left-to-right',
        gradientColors: ['#ff8800', '#ff0000'],
      },
      '#8b5cf6',
    )

    expect(nextLayer).toEqual(
      expect.objectContaining({
        colorMode: 'gradient',
        gradientDirection: 'left-to-right',
        gradientColors: ['#ff8800', '#ff0000'],
        color: expect.objectContaining({
          mode: 'gradient',
          gradientDirection: 'left-to-right',
          gradientColors: ['#ff8800', '#ff0000'],
        }),
      }),
    )
  })

  it('normalizes invalid gradient payloads back to a safe two-stop gradient', () => {
    expect(normalizeSpectrumGradientColors([{ value: 'bad-color' }], '#7c3aed')).toEqual([
      '#7c3aed',
      '#22d3ee',
    ])
  })

  it('builds the preset value from normalized gradient colors', () => {
    expect(buildSpectrumGradientPresetValue(['#ff8800', '#ff0000'])).toBe('#ff8800,#ff0000')
  })
})
