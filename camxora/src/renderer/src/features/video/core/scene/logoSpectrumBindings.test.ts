import { buildVideoTemplateDraft } from '@/features/video/core/contracts/videoTemplateDraft'
import {
  applyLogoShapeDraftChange,
  applyLogoSizeDraftChange,
  applySpectrumAttachToLogoDraftChange,
} from '@/features/video/core/scene/logoSpectrumBindings'

describe('logoSpectrumBindings', () => {
  it('recomputes the spectrum gap when logo shape changes while attached', () => {
    const draft = buildVideoTemplateDraft(
      {
        previewBindings: { spectrumAttachToLogo: true, spectrumLogoGap: 20 },
        logoSettings: { circleMask: true, size: 200 },
      },
      { logoPath: 'D:/logo.png' },
    )

    const next = applyLogoShapeDraftChange(draft, 'square')

    expect(next.logoShape).toBe('square')
    expect(next.spectrumLogoGap).toBeGreaterThan(draft.spectrumLogoGap)
  })

  it('keeps manual gap unchanged when spectrum is not attached to the logo', () => {
    const draft = buildVideoTemplateDraft(
      {
        previewBindings: { spectrumAttachToLogo: false, spectrumLogoGap: 33 },
        logoSettings: { circleMask: true, size: 200 },
      },
      { logoPath: 'D:/logo.png' },
    )

    const next = applyLogoShapeDraftChange(draft, 'square')

    expect(next.spectrumLogoGap).toBe(33)
  })

  it('recomputes the recommended gap when attachment is enabled', () => {
    const draft = buildVideoTemplateDraft(
      {
        previewBindings: { spectrumAttachToLogo: false, spectrumLogoGap: 18 },
        logoSettings: { circleMask: true, size: 300 },
      },
      { logoPath: 'D:/logo.png' },
    )

    const resized = applyLogoSizeDraftChange(draft, 6)
    const attached = applySpectrumAttachToLogoDraftChange(resized, true)

    expect(attached.spectrumAttachToLogo).toBe(true)
    expect(attached.spectrumLogoGap).toBeGreaterThan(18)
  })
})
