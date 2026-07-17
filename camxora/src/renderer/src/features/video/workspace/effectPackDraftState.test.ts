import { buildVideoTemplateDraft } from '@/features/video/core/contracts/videoTemplateDraft'
import {
  pickBackgroundDraftSlice,
  pickLogoDraftSlice,
  pickParticlesDraftSlice,
  pickSpectrumDraftSlice,
} from '@/features/video/workspace/templateDraftDomains'
import { buildAppliedEffectPackDraftState, buildClearedEffectPackDraftState } from '@/features/video/workspace/effectPackDraftState'

describe('effectPackDraftState', () => {
  it('keeps non-spectrum draft slices untouched when applying a spectrum pack preview', () => {
    const currentTemplate = {
      style: 'straight-bars',
      spectrumEnabled: true,
      audioSettings: {
        inputGain: 1.5,
        bandContrast: 1.1,
      },
      position: {
        anchor: 'center',
        x: 12,
        y: -6,
      },
      backgroundSettings: {
        fitMode: 'contain',
        brightness: 0.7,
        smoothing: 0.4,
      },
      logoSettings: {
        enabled: true,
        size: 260,
        opacity: 0.9,
      },
      particlesSettings: {
        enabled: true,
        style: 'spark',
        maxCount: 800,
      },
      textOverlays: [
        {
          id: 'text-1',
          text: 'Boss',
        },
      ],
      layers: [
        { name: 'Base', thickness: 20 },
      ],
    }
    const currentDraft = buildVideoTemplateDraft(currentTemplate, { logoPath: 'D:/logo.png' })

    const result = buildAppliedEffectPackDraftState({
      currentDraft,
      currentTemplate,
      workspace: { logoPath: 'D:/logo.png' },
      domain: 'spectrum',
      item: {
        packId: 'pack.spectrum.alpha',
        version: '1.0.0',
        templatePatch: {
          style: 'flying-glow',
          audioSettings: {
            inputGain: 4.5,
          },
          layers: [
            { name: 'Pack Layer', thickness: 32 },
          ],
        },
      },
    })

    expect(pickSpectrumDraftSlice(result.nextDraft)).toMatchObject({
      style: 'flying-glow',
      audioInputGain: 4.5,
      effectPackSelection: {
        packId: 'pack.spectrum.alpha',
        version: '1.0.0',
      },
    })
    expect(pickBackgroundDraftSlice(result.nextDraft)).toEqual(pickBackgroundDraftSlice(currentDraft))
    expect(pickLogoDraftSlice(result.nextDraft)).toEqual(pickLogoDraftSlice(currentDraft))
    expect(pickParticlesDraftSlice(result.nextDraft)).toEqual(pickParticlesDraftSlice(currentDraft))
    expect(result.nextLayers).toEqual([{ name: 'Pack Layer', thickness: 32 }])
  })

  it('clears only the requested domain reference without mutating the rest of the draft', () => {
    const currentDraft = buildVideoTemplateDraft(
      {
        effectPacks: {
          particles: {
            packId: 'pack.particles.alpha',
            version: '2.0.0',
          },
        },
        particlesSettings: {
          enabled: true,
          style: 'glow',
        },
        logoSettings: {
          enabled: true,
          size: 240,
        },
      },
      { logoPath: 'D:/logo.png' },
    )

    const result = buildClearedEffectPackDraftState({
      currentDraft,
      domain: 'particles',
    })

    expect(result.nextDraft.effectPacks.particles).toBeNull()
    expect(result.nextDraft.logoEnabled).toBe(currentDraft.logoEnabled)
    expect(result.nextDraft.logoSizeStep).toBe(currentDraft.logoSizeStep)
    expect(result.templatePatch).toEqual({
      effectPacks: {
        particles: null,
      },
    })
  })
})
