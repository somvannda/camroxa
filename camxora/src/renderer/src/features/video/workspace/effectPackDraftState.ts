import type { VideoWorkspaceState } from '@/shared/types/desktop'
import {
  buildVideoTemplateDraft,
  type VideoTemplateDraft,
} from '@/features/video/core/contracts/videoTemplateDraft'
import {
  cloneLayerRecords,
} from '@/features/video/workspace/videoWorkspaceDraftStore'
import {
  pickBackgroundDraftSlice,
  pickLogoDraftSlice,
  pickParticlesDraftSlice,
  pickSpectrumDraftSlice,
} from '@/features/video/workspace/templateDraftDomains'
import type {
  EffectPackCatalogItem,
  EffectPackDomain,
} from '@shared/effectPacks/effectPackContracts'
import {
  buildTemplateEffectPackApplyPatch,
  buildTemplateEffectPackReferencePatch,
} from '@shared/effectPacks/effectPackRuntime'

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function mergeRecords(base: Record<string, unknown>, patch: Record<string, unknown>): Record<string, unknown> {
  const next: Record<string, unknown> = { ...base }
  Object.entries(patch).forEach(([key, value]) => {
    if (isRecord(value) && isRecord(next[key])) {
      next[key] = mergeRecords(next[key] as Record<string, unknown>, value)
      return
    }
    next[key] = value
  })
  return next
}

function mergeSpectrumDraft(nextDraft: VideoTemplateDraft, resolvedDraft: VideoTemplateDraft): VideoTemplateDraft {
  const { effectPackSelection: _selection, ...spectrumSlice } = pickSpectrumDraftSlice(resolvedDraft)
  return {
    ...nextDraft,
    ...spectrumSlice,
    effectPacks: resolvedDraft.effectPacks,
  }
}

function mergeBackgroundDraft(nextDraft: VideoTemplateDraft, resolvedDraft: VideoTemplateDraft): VideoTemplateDraft {
  const { effectPackSelection: _selection, ...backgroundSlice } = pickBackgroundDraftSlice(resolvedDraft)
  return {
    ...nextDraft,
    ...backgroundSlice,
    effectPacks: resolvedDraft.effectPacks,
  }
}

function mergeLogoDraft(nextDraft: VideoTemplateDraft, resolvedDraft: VideoTemplateDraft): VideoTemplateDraft {
  const { effectPackSelection: _selection, ...logoSlice } = pickLogoDraftSlice(resolvedDraft)
  return {
    ...nextDraft,
    ...logoSlice,
    effectPacks: resolvedDraft.effectPacks,
  }
}

function mergeParticlesDraft(nextDraft: VideoTemplateDraft, resolvedDraft: VideoTemplateDraft): VideoTemplateDraft {
  const { effectPackSelection: _selection, ...particlesSlice } = pickParticlesDraftSlice(resolvedDraft)
  return {
    ...nextDraft,
    ...particlesSlice,
    effectPacks: resolvedDraft.effectPacks,
  }
}

export function buildAppliedEffectPackDraftState(options: {
  currentDraft: VideoTemplateDraft
  currentTemplate: Record<string, unknown>
  workspace: Pick<VideoWorkspaceState, 'logoPath'>
  domain: EffectPackDomain
  item: Pick<EffectPackCatalogItem, 'packId' | 'version' | 'templatePatch'>
}): {
  nextDraft: VideoTemplateDraft
  nextLayers: Record<string, unknown>[] | null
  templatePatch: Record<string, unknown>
} {
  const templatePatch = buildTemplateEffectPackApplyPatch(options.domain, options.item)
  const nextTemplate = mergeRecords(options.currentTemplate, templatePatch)
  const resolvedDraft = buildVideoTemplateDraft(nextTemplate, options.workspace)

  switch (options.domain) {
    case 'background':
      return {
        nextDraft: mergeBackgroundDraft(options.currentDraft, resolvedDraft),
        nextLayers: null,
        templatePatch,
      }
    case 'logo':
      return {
        nextDraft: mergeLogoDraft(options.currentDraft, resolvedDraft),
        nextLayers: null,
        templatePatch,
      }
    case 'particles':
      return {
        nextDraft: mergeParticlesDraft(options.currentDraft, resolvedDraft),
        nextLayers: null,
        templatePatch,
      }
    case 'spectrum':
    default:
      return {
        nextDraft: mergeSpectrumDraft(options.currentDraft, resolvedDraft),
        nextLayers: cloneLayerRecords(nextTemplate.layers),
        templatePatch,
      }
  }
}

export function buildClearedEffectPackDraftState(options: {
  currentDraft: VideoTemplateDraft
  domain: EffectPackDomain
}): {
  nextDraft: VideoTemplateDraft
  templatePatch: Record<string, unknown>
} {
  const templatePatch = buildTemplateEffectPackReferencePatch(options.domain, null)
  return {
    nextDraft: {
      ...options.currentDraft,
      effectPacks: {
        ...options.currentDraft.effectPacks,
        [options.domain]: null,
      },
    },
    templatePatch,
  }
}
