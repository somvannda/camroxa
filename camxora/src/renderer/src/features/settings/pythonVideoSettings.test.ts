import { buildSpectrumPresetTemplate } from '@/features/video/domains/spectrum/spectrumStyleRegistry'

describe('buildSpectrumPresetTemplate', () => {
  it('starts each curated preset with exactly one layer', () => {
    const template = {
      style: 'straight-bars',
      layers: [
        {
          id: 'layer-1',
          color: {
            mode: 'solid',
            solidColor: '#ffffff',
          },
        },
      ],
    }

    const presetKeys = [
      'straight-bars',
      'flying-glow',
      'orbital-bars',
      'dot-matrix',
      'wave-ribbon',
      'liquid-mass',
      'halo-stack',
    ]

    presetKeys.forEach((presetKey) => {
      const next = buildSpectrumPresetTemplate(template, presetKey)
      expect(next).not.toBeNull()
      expect(Array.isArray(next?.layers)).toBe(true)
      expect(next?.layers).toHaveLength(1)
    })
  })

  it('makes Flying Glow start as a curved mirrored wing recipe', () => {
    const template = {
      style: 'straight-bars',
      layers: [
        {
          id: 'layer-1',
          color: {
            mode: 'solid',
            solidColor: '#ffffff',
          },
        },
      ],
    }

    const next = buildSpectrumPresetTemplate(template, 'flying-glow')

    expect(next).not.toBeNull()
    expect(next?.style).toBe('flying-glow')
    expect(next?.layers).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          curved: true,
          mirrored: true,
          gravity: 'bottom',
          barWidth: 7,
        }),
      ]),
    )
  })

  it('makes Orbital Bars start as a curved mirrored circular-bar recipe', () => {
    const template = {
      style: 'straight-bars',
      layers: [
        {
          id: 'layer-1',
          color: {
            mode: 'solid',
            solidColor: '#ffffff',
          },
        },
      ],
    }

    const next = buildSpectrumPresetTemplate(template, 'orbital-bars')

    expect(next).not.toBeNull()
    expect(next?.style).toBe('orbital-bars')
    expect(next?.layers).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          curved: true,
          mirrored: true,
          gravity: 'bottom',
          barWidth: 5.5,
          color: expect.objectContaining({
            gradientDirection: 'circular',
          }),
        }),
      ]),
    )
  })
})
