import type { VideoWorkspaceState } from '@/shared/types/desktop'
import {
  readTemplateEffectPackMap,
} from '@shared/effectPacks/effectPackRuntime'
import type { TemplateEffectPackMap } from '@shared/effectPacks/effectPackContracts'
import type { PreviewDraftSource } from '@/features/video/core/contracts/previewDraftContracts'
import {
  buildAtmosphereSettingsState,
  type AtmosphereSettingsState,
} from '@/features/video/domains/atmosphere/atmosphereSettings'
import {
  buildBackgroundSettingsState,
  type BackgroundSettingsState,
} from '@/features/video/domains/background/backgroundSettings'
import {
  buildLogoSettingsState,
  type LogoSettingsState,
} from '@/features/video/domains/logo/logoSettings'
import {
  buildParticleSettingsState,
  type ParticleSettingsState,
} from '@/features/video/domains/particles/particleSettings'
import {
  buildSpectrumSettingsState,
  getRecommendedSpectrumLogoGap,
  type SpectrumSettingsState,
} from '@/features/video/domains/spectrum/spectrumSettings'
import {
  buildDefaultTextOverlayDraft,
  buildTextSettingsState,
  type TemplateTextOverlayDraft,
  type TextSettingsState,
} from '@/features/video/domains/text/textSettings'

export type VideoTemplateDraft = PreviewDraftSource &
  TextSettingsState & {
    effectPacks: TemplateEffectPackMap
  }

export {
  buildDefaultTextOverlayDraft,
  getRecommendedSpectrumLogoGap,
  type TemplateTextOverlayDraft,
}

export function buildVideoTemplateDraft(
  template: Record<string, unknown>,
  workspace: { logoPath: string } | Pick<VideoWorkspaceState, 'logoPath'>,
): VideoTemplateDraft {
  const logoState = buildLogoSettingsState(template, workspace)

  return {
    ...buildSpectrumSettingsState(template, logoState.logoShape, logoState.logoSizeStep),
    ...buildBackgroundSettingsState(template),
    ...buildAtmosphereSettingsState(template),
    ...logoState,
    ...buildParticleSettingsState(template),
    ...buildTextSettingsState(template),
    effectPacks: readTemplateEffectPackMap(template),
  }
}

export type {
  AtmosphereSettingsState,
  BackgroundSettingsState,
  LogoSettingsState,
  ParticleSettingsState,
  SpectrumSettingsState,
  TextSettingsState,
}
