import { buildAtmosphereTemplatePatch } from '@/features/video/domains/atmosphere/atmosphereSettings'
import { buildBackgroundTemplatePatch } from '@/features/video/domains/background/backgroundSettings'
import { buildLogoTemplatePatch } from '@/features/video/domains/logo/logoSettings'
import { buildParticlesTemplatePatch } from '@/features/video/domains/particles/particleSettings'
import { buildSpectrumTemplatePatch } from '@/features/video/domains/spectrum/spectrumSettings'
import { buildTextTemplatePatch } from '@/features/video/domains/text/textSettings'
import type { VideoTemplateDraft } from '@/features/video/core/contracts/videoTemplateDraft'

export function buildVideoWorkspaceTemplateSavePatch(options: {
  template: Record<string, unknown>
  draft: VideoTemplateDraft
  templateName: string
  layers: Record<string, unknown>[]
}): Record<string, unknown> {
  const templateName = String(options.templateName || '').trim()
  const effectPacks = {
    spectrum: options.draft.effectPacks.spectrum
      ? {
          packId: options.draft.effectPacks.spectrum.packId,
          version: options.draft.effectPacks.spectrum.version,
        }
      : null,
    background: options.draft.effectPacks.background
      ? {
          packId: options.draft.effectPacks.background.packId,
          version: options.draft.effectPacks.background.version,
        }
      : null,
    logo: options.draft.effectPacks.logo
      ? {
          packId: options.draft.effectPacks.logo.packId,
          version: options.draft.effectPacks.logo.version,
        }
      : null,
    particles: options.draft.effectPacks.particles
      ? {
          packId: options.draft.effectPacks.particles.packId,
          version: options.draft.effectPacks.particles.version,
        }
      : null,
  }

  return {
    templateName,
    effectPacks,
    ...buildSpectrumTemplatePatch(options.template, options.draft),
    ...buildBackgroundTemplatePatch(options.template, options.draft),
    ...buildAtmosphereTemplatePatch(options.template, options.draft),
    ...buildLogoTemplatePatch(options.template, options.draft),
    ...buildParticlesTemplatePatch(options.template, options.draft),
    ...buildTextTemplatePatch(options.draft),
    layers: options.layers.map((layer) => ({ ...layer })),
  }
}
