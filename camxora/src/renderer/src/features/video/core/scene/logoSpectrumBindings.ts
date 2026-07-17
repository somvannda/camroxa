import type { LogoSpectrumBindingDraft } from '@/features/video/core/contracts/previewDraftContracts'
import { getRecommendedSpectrumLogoGap } from '@/features/video/domains/spectrum/spectrumSettings'

export function applyLogoShapeDraftChange<TDraft extends LogoSpectrumBindingDraft>(
  draft: TDraft,
  logoShape: string,
): TDraft {
  return {
    ...draft,
    logoShape,
    spectrumLogoGap: draft.spectrumAttachToLogo
      ? getRecommendedSpectrumLogoGap(logoShape, draft.logoSizeStep)
      : draft.spectrumLogoGap,
  }
}

export function applyLogoSizeDraftChange<TDraft extends LogoSpectrumBindingDraft>(
  draft: TDraft,
  logoSizeStep: number,
): TDraft {
  return {
    ...draft,
    logoSizeStep,
  }
}

export function applySpectrumAttachToLogoDraftChange<TDraft extends LogoSpectrumBindingDraft>(
  draft: TDraft,
  attachToLogo: boolean,
): TDraft {
  return {
    ...draft,
    spectrumAttachToLogo: attachToLogo,
    spectrumLogoGap: attachToLogo
      ? getRecommendedSpectrumLogoGap(draft.logoShape, draft.logoSizeStep)
      : draft.spectrumLogoGap,
  }
}
