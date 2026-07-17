import type { TemplateSettingsDraft } from '@/features/settings/settingsTemplateDraft'

export type VideoWorkspaceDraftSnapshot = {
  templateName: string
  draft: TemplateSettingsDraft
  layers: Record<string, unknown>[]
}

type LegacySpectrumSessionSnapshot = {
  style?: unknown
  spectrumEnabled?: unknown
  audioInputGain?: unknown
  audioBarHeight?: unknown
  audioBandContrast?: unknown
  audioTransientFocus?: unknown
  audioKickImpact?: unknown
  audioBassEmphasis?: unknown
  audioTrebleShimmer?: unknown
  audioPeakHoldBlend?: unknown
  audioMotionSmoothing?: unknown
  flyingGlowWingMotionSpeed?: unknown
  flyingGlowWingRelease?: unknown
  spectrumAttachToLogo?: unknown
  spectrumLogoGap?: unknown
  anchor?: unknown
  positionX?: unknown
  positionY?: unknown
  layers?: unknown
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

export function cloneLayerRecords(rawLayers: unknown): Record<string, unknown>[] {
  return Array.isArray(rawLayers)
    ? rawLayers.map((layer) =>
        typeof layer === 'object' && layer !== null && !Array.isArray(layer)
          ? { ...(layer as Record<string, unknown>) }
          : {},
      )
    : []
}

function getWorkspaceDraftStorageKey(prefix: string, templateId: string): string {
  return `${prefix}.${templateId}`
}

function applyLegacySpectrumFields(
  draft: TemplateSettingsDraft,
  parsed: LegacySpectrumSessionSnapshot,
): TemplateSettingsDraft {
  if (
    parsed.style === undefined &&
    parsed.spectrumEnabled === undefined &&
    parsed.audioInputGain === undefined &&
    parsed.audioBarHeight === undefined &&
    parsed.audioBandContrast === undefined &&
    parsed.audioTransientFocus === undefined &&
    parsed.audioKickImpact === undefined &&
    parsed.audioBassEmphasis === undefined &&
    parsed.audioTrebleShimmer === undefined &&
    parsed.audioPeakHoldBlend === undefined &&
    parsed.audioMotionSmoothing === undefined &&
    parsed.flyingGlowWingMotionSpeed === undefined &&
    parsed.flyingGlowWingRelease === undefined &&
    parsed.spectrumAttachToLogo === undefined &&
    parsed.spectrumLogoGap === undefined &&
    parsed.anchor === undefined &&
    parsed.positionX === undefined &&
    parsed.positionY === undefined
  ) {
    return draft
  }

  return {
    ...draft,
    style: typeof parsed.style === 'string' ? parsed.style : draft.style,
    spectrumEnabled:
      typeof parsed.spectrumEnabled === 'boolean' ? parsed.spectrumEnabled : draft.spectrumEnabled,
    audioInputGain:
      typeof parsed.audioInputGain === 'number' ? parsed.audioInputGain : draft.audioInputGain,
    audioBarHeight:
      typeof parsed.audioBarHeight === 'number' ? parsed.audioBarHeight : draft.audioBarHeight,
    audioBandContrast:
      typeof parsed.audioBandContrast === 'number' ? parsed.audioBandContrast : draft.audioBandContrast,
    audioTransientFocus:
      typeof parsed.audioTransientFocus === 'number' ? parsed.audioTransientFocus : draft.audioTransientFocus,
    audioKickImpact:
      typeof parsed.audioKickImpact === 'number' ? parsed.audioKickImpact : draft.audioKickImpact,
    audioBassEmphasis:
      typeof parsed.audioBassEmphasis === 'number' ? parsed.audioBassEmphasis : draft.audioBassEmphasis,
    audioTrebleShimmer:
      typeof parsed.audioTrebleShimmer === 'number' ? parsed.audioTrebleShimmer : draft.audioTrebleShimmer,
    audioPeakHoldBlend:
      typeof parsed.audioPeakHoldBlend === 'number' ? parsed.audioPeakHoldBlend : draft.audioPeakHoldBlend,
    audioMotionSmoothing:
      typeof parsed.audioMotionSmoothing === 'number'
        ? parsed.audioMotionSmoothing
        : draft.audioMotionSmoothing,
    flyingGlowWingMotionSpeed:
      typeof parsed.flyingGlowWingMotionSpeed === 'number'
        ? parsed.flyingGlowWingMotionSpeed
        : draft.flyingGlowWingMotionSpeed,
    flyingGlowWingRelease:
      typeof parsed.flyingGlowWingRelease === 'number'
        ? parsed.flyingGlowWingRelease
        : draft.flyingGlowWingRelease,
    spectrumAttachToLogo:
      typeof parsed.spectrumAttachToLogo === 'boolean'
        ? parsed.spectrumAttachToLogo
        : draft.spectrumAttachToLogo,
    spectrumLogoGap:
      typeof parsed.spectrumLogoGap === 'number' ? parsed.spectrumLogoGap : draft.spectrumLogoGap,
    anchor: typeof parsed.anchor === 'string' ? parsed.anchor : draft.anchor,
    positionX: typeof parsed.positionX === 'number' ? parsed.positionX : draft.positionX,
    positionY: typeof parsed.positionY === 'number' ? parsed.positionY : draft.positionY,
  }
}

export function readVideoWorkspaceDraftSnapshot(
  storagePrefix: string,
  templateId: string,
  persistedDraft: TemplateSettingsDraft,
  persistedTemplateName: string,
): VideoWorkspaceDraftSnapshot | null {
  if (!templateId || typeof window === 'undefined') {
    return null
  }
  try {
    const rawValue = window.localStorage.getItem(getWorkspaceDraftStorageKey(storagePrefix, templateId))
    if (!rawValue) {
      return null
    }
    const parsed = JSON.parse(rawValue) as {
      templateName?: unknown
      draft?: unknown
      layers?: unknown
    } & LegacySpectrumSessionSnapshot
    if (!parsed || typeof parsed !== 'object') {
      return null
    }

    const draft = isRecord(parsed.draft)
      ? ({ ...persistedDraft, ...(parsed.draft as TemplateSettingsDraft) } as TemplateSettingsDraft)
      : applyLegacySpectrumFields(persistedDraft, parsed)

    return {
      templateName:
        typeof parsed.templateName === 'string' ? parsed.templateName : persistedTemplateName,
      draft,
      layers: cloneLayerRecords(parsed.layers),
    }
  } catch {
    return null
  }
}

export function writeVideoWorkspaceDraftSnapshot(
  storagePrefix: string,
  templateId: string,
  snapshot: VideoWorkspaceDraftSnapshot,
): void {
  if (!templateId || typeof window === 'undefined') {
    return
  }
  try {
    window.localStorage.setItem(
      getWorkspaceDraftStorageKey(storagePrefix, templateId),
      JSON.stringify({
        templateName: snapshot.templateName,
        draft: snapshot.draft,
        layers: cloneLayerRecords(snapshot.layers),
      }),
    )
  } catch {
    // Ignore storage failures; the in-memory draft still exists.
  }
}

export function clearVideoWorkspaceDraftSnapshot(
  storagePrefix: string,
  templateId: string,
): void {
  if (!templateId || typeof window === 'undefined') {
    return
  }
  try {
    window.localStorage.removeItem(getWorkspaceDraftStorageKey(storagePrefix, templateId))
  } catch {
    // Ignore storage failures.
  }
}
