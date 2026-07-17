import type { VideoWorkspaceState } from '@/shared/types/desktop'
import {
  buildAtmosphereTemplatePatch,
} from '@/features/video/domains/atmosphere/atmosphereSettings'
import {
  buildBackgroundTemplatePatch as buildBackgroundDomainTemplatePatch,
} from '@/features/video/domains/background/backgroundSettings'
import {
  buildLogoTemplatePatch as buildLogoDomainTemplatePatch,
} from '@/features/video/domains/logo/logoSettings'
import {
  buildParticlesTemplatePatch as buildParticlesDomainTemplatePatch,
} from '@/features/video/domains/particles/particleSettings'
import {
  buildSpectrumTemplatePatch as buildSpectrumDomainTemplatePatch,
} from '@/features/video/domains/spectrum/spectrumSettings'
import {
  buildTextTemplatePatch as buildTextDomainTemplatePatch,
} from '@/features/video/domains/text/textSettings'
import {
  buildVideoTemplateDraft,
  getRecommendedSpectrumLogoGap,
  buildDefaultTextOverlayDraft,
  type TemplateTextOverlayDraft,
  type VideoTemplateDraft,
} from '@/features/video/core/contracts/videoTemplateDraft'
import { buildVideoWorkspaceTemplateSavePatch } from '@/features/video/workspace/videoWorkspaceTemplateSave'

export type TemplateSettingsDraft = VideoTemplateDraft

export { buildDefaultTextOverlayDraft, getRecommendedSpectrumLogoGap, type TemplateTextOverlayDraft }

export function buildTemplateDraft(
  template: Record<string, unknown>,
  workspace: { logoPath: string } | Pick<VideoWorkspaceState, 'logoPath'>,
): TemplateSettingsDraft {
  return buildVideoTemplateDraft(template, workspace)
}

export function buildSpectrumTemplatePatch(
  template: Record<string, unknown>,
  draft: TemplateSettingsDraft,
): Record<string, unknown> {
  return buildSpectrumDomainTemplatePatch(template, draft)
}

export function buildBackgroundTemplatePatch(
  template: Record<string, unknown>,
  draft: TemplateSettingsDraft,
): Record<string, unknown> {
  return {
    ...buildBackgroundDomainTemplatePatch(template, draft),
    ...buildAtmosphereTemplatePatch(template, draft),
  }
}

export function buildLogoTemplatePatch(
  template: Record<string, unknown>,
  draft: TemplateSettingsDraft,
): Record<string, unknown> {
  return buildLogoDomainTemplatePatch(template, draft)
}

export function buildParticlesTemplatePatch(
  template: Record<string, unknown>,
  draft: TemplateSettingsDraft,
): Record<string, unknown> {
  return buildParticlesDomainTemplatePatch(template, draft)
}

export function buildTextTemplatePatch(draft: TemplateSettingsDraft): Record<string, unknown> {
  return buildTextDomainTemplatePatch(draft)
}

export { buildVideoWorkspaceTemplateSavePatch }
