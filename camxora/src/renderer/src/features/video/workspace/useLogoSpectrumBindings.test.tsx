import { act, renderHook } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { buildTemplateDraft } from '@/features/settings/settingsTemplateDraft'
import { useLogoSpectrumBindings } from '@/features/video/workspace/useLogoSpectrumBindings'

describe('useLogoSpectrumBindings', () => {
  it('updates logo shape through both logo and spectrum coordinators', () => {
    const templateDraft = buildTemplateDraft(
      {
        previewBindings: {
          spectrumAttachToLogo: true,
          spectrumLogoGap: 18,
        },
        logoSettings: {
          enabled: true,
          circleMask: true,
          size: 300,
        },
      },
      { logoPath: 'D:/logo.png' },
    )

    const commitLogoDraft = vi.fn()
    const commitSpectrumSessionDraft = vi.fn()

    const { result } = renderHook(() =>
      useLogoSpectrumBindings({
        commitLogoDraft,
        commitSpectrumSessionDraft,
        templateDraft,
      }),
    )

    act(() => {
      result.current.applyLogoShape('square')
    })

    expect(commitSpectrumSessionDraft).toHaveBeenCalledWith(
      expect.objectContaining({
        logoShape: 'square',
      }),
    )
    expect(commitLogoDraft).toHaveBeenCalledWith(
      expect.objectContaining({
        logoShape: 'square',
      }),
    )
  })

  it('patches logo-only draft values without touching the spectrum-local draft path', () => {
    const templateDraft = buildTemplateDraft(
      {
        logoSettings: {
          enabled: true,
          opacity: 0.8,
          size: 220,
        },
      },
      { logoPath: 'D:/logo.png' },
    )

    const commitLogoDraft = vi.fn()
    const commitSpectrumSessionDraft = vi.fn()

    const { result } = renderHook(() =>
      useLogoSpectrumBindings({
        commitLogoDraft,
        commitSpectrumSessionDraft,
        templateDraft,
      }),
    )

    act(() => {
      result.current.patchLogoDraft({ logoOpacity: 0.45 })
    })

    expect(commitLogoDraft).toHaveBeenCalledWith(
      expect.objectContaining({
        logoOpacity: 0.45,
      }),
    )
    expect(commitSpectrumSessionDraft).not.toHaveBeenCalled()
  })
})
