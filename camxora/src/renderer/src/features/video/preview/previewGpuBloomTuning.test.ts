import {
  buildPreviewGpuBloomPass,
  computeSpectrumBloomStats,
} from '@/features/video/preview/previewGpuBloomTuning'

describe('previewGpuBloomTuning', () => {
  const baseDraft = {
    particlesEnabled: true,
    spectrumEnabled: true,
    style: 'straight-bars',
  } as const

  it('gives halo stack a softer threshold and broader knee than straight bars', () => {
    const straightStats = computeSpectrumBloomStats([
      { glow: 18, blur: 4, blendMode: 'normal', styleKey: 'straight-bars' },
    ])
    const haloStats = computeSpectrumBloomStats([
      { glow: 64, blur: 10, blendMode: 'screen', styleKey: 'halo-stack' },
    ])

    const straightPostFx = buildPreviewGpuBloomPass(baseDraft as never, straightStats, 0.6)
    const haloPostFx = buildPreviewGpuBloomPass(baseDraft as never, haloStats, 0.6)

    expect(straightPostFx).not.toBeNull()
    expect(haloPostFx).not.toBeNull()
    expect((haloPostFx?.threshold ?? 1) < (straightPostFx?.threshold ?? 0)).toBe(true)
    expect((haloPostFx?.knee ?? 0) > (straightPostFx?.knee ?? 1)).toBe(true)
    expect((haloPostFx?.bloomStrength ?? 0) > (straightPostFx?.bloomStrength ?? 1)).toBe(true)
  })

  it('keeps liquid mass bloom tighter than halo stack', () => {
    const liquidStats = computeSpectrumBloomStats([
      { glow: 20, blur: 4, blendMode: 'normal', styleKey: 'liquid-mass' },
    ])
    const haloStats = computeSpectrumBloomStats([
      { glow: 64, blur: 10, blendMode: 'screen', styleKey: 'halo-stack' },
    ])

    const liquidPostFx = buildPreviewGpuBloomPass(baseDraft as never, liquidStats, 0.55)
    const haloPostFx = buildPreviewGpuBloomPass(baseDraft as never, haloStats, 0.55)

    expect(liquidPostFx).not.toBeNull()
    expect(haloPostFx).not.toBeNull()
    expect((liquidPostFx?.blurScale ?? 10) < (haloPostFx?.blurScale ?? 0)).toBe(true)
    expect((liquidPostFx?.bloomStrength ?? 10) < (haloPostFx?.bloomStrength ?? 0)).toBe(true)
  })

  it('keeps straight bars bloom tighter than wave ribbon', () => {
    const straightStats = computeSpectrumBloomStats([
      { glow: 14, blur: 2, blendMode: 'normal', styleKey: 'straight-bars' },
    ])
    const waveStats = computeSpectrumBloomStats([
      { glow: 24, blur: 6, blendMode: 'screen', styleKey: 'wave-ribbon' },
    ])

    const straightPostFx = buildPreviewGpuBloomPass(baseDraft as never, straightStats, 0.58)
    const wavePostFx = buildPreviewGpuBloomPass(baseDraft as never, waveStats, 0.58)

    expect(straightPostFx).not.toBeNull()
    expect(wavePostFx).not.toBeNull()
    expect((straightPostFx?.blurScale ?? 10) < (wavePostFx?.blurScale ?? 0)).toBe(true)
    expect((straightPostFx?.knee ?? 10) < (wavePostFx?.knee ?? 0)).toBe(true)
  })

  it('keeps flying glow bloom tighter than wave ribbon so the wing surface stays crisp', () => {
    const flyingGlowStats = computeSpectrumBloomStats([
      { glow: 14, blur: 0.6, blendMode: 'normal', styleKey: 'flying-glow' },
    ])
    const waveStats = computeSpectrumBloomStats([
      { glow: 24, blur: 6, blendMode: 'screen', styleKey: 'wave-ribbon' },
    ])

    const flyingGlowPostFx = buildPreviewGpuBloomPass(
      { ...baseDraft, style: 'flying-glow' } as never,
      flyingGlowStats,
      0.58,
    )
    const wavePostFx = buildPreviewGpuBloomPass(
      { ...baseDraft, style: 'wave-ribbon' } as never,
      waveStats,
      0.58,
    )

    expect(flyingGlowPostFx).not.toBeNull()
    expect(wavePostFx).not.toBeNull()
    expect((flyingGlowPostFx?.blurScale ?? 10) < (wavePostFx?.blurScale ?? 0)).toBe(true)
    expect((flyingGlowPostFx?.bloomStrength ?? 10) < (wavePostFx?.bloomStrength ?? 0)).toBe(true)
    expect((flyingGlowPostFx?.threshold ?? 0) > (wavePostFx?.threshold ?? 1)).toBe(true)
  })
})
