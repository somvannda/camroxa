import type { TemplateSettingsDraft } from '@/features/settings/settingsTemplateDraft'
import type { EffectPackTemplateReference } from '@shared/effectPacks/effectPackContracts'
import type { AtmosphereSettingsState } from '@/features/video/domains/atmosphere/atmosphereSettings'
import type { BackgroundSettingsState } from '@/features/video/domains/background/backgroundSettings'
import type { LogoSettingsState } from '@/features/video/domains/logo/logoSettings'
import type { ParticleSettingsState } from '@/features/video/domains/particles/particleSettings'
import type { SpectrumSettingsState } from '@/features/video/domains/spectrum/spectrumSettings'
import type { TextSettingsState } from '@/features/video/domains/text/textSettings'

type EffectPackSelectionDraft = {
  effectPackSelection: EffectPackTemplateReference | null
}

export type SpectrumDraftSlice = SpectrumSettingsState & EffectPackSelectionDraft
export type BackgroundDraftSlice = BackgroundSettingsState & AtmosphereSettingsState & EffectPackSelectionDraft
export type LogoDraftSlice = LogoSettingsState &
  Pick<SpectrumSettingsState, 'spectrumAttachToLogo' | 'spectrumLogoGap'> &
  EffectPackSelectionDraft
export type ParticlesDraftSlice = ParticleSettingsState & EffectPackSelectionDraft
export type TextDraftSlice = TextSettingsState

export type VideoWorkspaceDraftSlices = {
  spectrum: SpectrumDraftSlice
  background: BackgroundDraftSlice
  logo: LogoDraftSlice
  particles: ParticlesDraftSlice
  text: TextDraftSlice
}

export type VideoWorkspaceDraftDirtyState = Record<keyof VideoWorkspaceDraftSlices, boolean>

function serializeSlice(value: unknown): string {
  return JSON.stringify(value)
}

export function pickSpectrumDraftSlice(draft: TemplateSettingsDraft): SpectrumDraftSlice {
  return {
    spectrumEnabled: draft.spectrumEnabled,
    style: draft.style,
    audioInputGain: draft.audioInputGain,
    audioBarHeight: draft.audioBarHeight,
    audioBandContrast: draft.audioBandContrast,
    audioTransientFocus: draft.audioTransientFocus,
    audioKickImpact: draft.audioKickImpact,
    audioBassEmphasis: draft.audioBassEmphasis,
    audioTrebleShimmer: draft.audioTrebleShimmer,
    audioPeakHoldBlend: draft.audioPeakHoldBlend,
    audioMotionSmoothing: draft.audioMotionSmoothing,
    flyingGlowWingMotionSpeed: draft.flyingGlowWingMotionSpeed,
    flyingGlowWingRelease: draft.flyingGlowWingRelease,
    spectrumAttachToLogo: draft.spectrumAttachToLogo,
    spectrumLogoGap: draft.spectrumLogoGap,
    anchor: draft.anchor,
    positionX: draft.positionX,
    positionY: draft.positionY,
    effectPackSelection: draft.effectPacks.spectrum ?? null,
  }
}

export function pickBackgroundDraftSlice(draft: TemplateSettingsDraft): BackgroundDraftSlice {
  return {
    backgroundEnabled: draft.backgroundEnabled,
    backgroundFitMode: draft.backgroundFitMode,
    backgroundUserScale: draft.backgroundUserScale,
    backgroundBrightness: draft.backgroundBrightness,
    backgroundReactivity: draft.backgroundReactivity,
    backgroundSmoothing: draft.backgroundSmoothing,
    backgroundMotionMode: draft.backgroundMotionMode,
    backgroundMotionZoomStrength: draft.backgroundMotionZoomStrength,
    backgroundMotionVibrateStrength: draft.backgroundMotionVibrateStrength,
    backgroundMotionSpeed: draft.backgroundMotionSpeed,
    vignetteEnabled: draft.vignetteEnabled,
    vignetteStrength: draft.vignetteStrength,
    vignetteFeather: draft.vignetteFeather,
    vignetteOpacity: draft.vignetteOpacity,
    vignetteColor: draft.vignetteColor,
    smokeEnabled: draft.smokeEnabled,
    smokeStrength: draft.smokeStrength,
    smokeBlur: draft.smokeBlur,
    smokeNoise: draft.smokeNoise,
    smokeSpeed: draft.smokeSpeed,
    smokeOpacity: draft.smokeOpacity,
    smokeColor: draft.smokeColor,
    effectPackSelection: draft.effectPacks.background ?? null,
  }
}

export function pickLogoDraftSlice(draft: TemplateSettingsDraft): LogoDraftSlice {
  return {
    logoEnabled: draft.logoEnabled,
    logoSpinEnabled: draft.logoSpinEnabled,
    logoSpinDirection: draft.logoSpinDirection,
    logoSpinSpeed: draft.logoSpinSpeed,
    logoPath: draft.logoPath,
    logoShape: draft.logoShape,
    logoSizeStep: draft.logoSizeStep,
    logoOpacity: draft.logoOpacity,
    logoReactivity: draft.logoReactivity,
    logoSmoothing: draft.logoSmoothing,
    logoMotionMode: draft.logoMotionMode,
    logoMotionZoomStrength: draft.logoMotionZoomStrength,
    logoMotionVibrateStrength: draft.logoMotionVibrateStrength,
    logoMotionSpeed: draft.logoMotionSpeed,
    spectrumAttachToLogo: draft.spectrumAttachToLogo,
    spectrumLogoGap: draft.spectrumLogoGap,
    effectPackSelection: draft.effectPacks.logo ?? null,
  }
}

export function pickParticlesDraftSlice(draft: TemplateSettingsDraft): ParticlesDraftSlice {
  return {
    particlesEnabled: draft.particlesEnabled,
    particlesMaxCount: draft.particlesMaxCount,
    particlesSpawnRate: draft.particlesSpawnRate,
    particlesLifetimeSec: draft.particlesLifetimeSec,
    particlesSpeed: draft.particlesSpeed,
    particlesReactivity: draft.particlesReactivity,
    particlesAudioMotionMode: draft.particlesAudioMotionMode,
    particlesAudioTravelBoost: draft.particlesAudioTravelBoost,
    particlesSmoothing: draft.particlesSmoothing,
    particlesSpawnMode: draft.particlesSpawnMode,
    particlesSpawnTrigger: draft.particlesSpawnTrigger,
    particlesSpawnThreshold: draft.particlesSpawnThreshold,
    particlesVariant: draft.particlesVariant,
    particlesSpawnArea: draft.particlesSpawnArea,
    particlesSizeJitter: draft.particlesSizeJitter,
    particlesDrift: draft.particlesDrift,
    particlesSwirl: draft.particlesSwirl,
    particlesStyle: draft.particlesStyle,
    particlesSize: draft.particlesSize,
    particlesOpacity: draft.particlesOpacity,
    particlesColor: draft.particlesColor,
    particlesReactColor: draft.particlesReactColor,
    particlesReactStrength: draft.particlesReactStrength,
    effectPackSelection: draft.effectPacks.particles ?? null,
  }
}

export function pickTextDraftSlice(draft: TemplateSettingsDraft): TextDraftSlice {
  return {
    textOverlays: draft.textOverlays,
  }
}

export function buildVideoWorkspaceDraftSlices(draft: TemplateSettingsDraft): VideoWorkspaceDraftSlices {
  return {
    spectrum: pickSpectrumDraftSlice(draft),
    background: pickBackgroundDraftSlice(draft),
    logo: pickLogoDraftSlice(draft),
    particles: pickParticlesDraftSlice(draft),
    text: pickTextDraftSlice(draft),
  }
}

export function buildVideoWorkspaceDraftDirtyState(
  localDraft: TemplateSettingsDraft | null,
  persistedDraft: TemplateSettingsDraft | null,
  options?: { spectrumDirty?: boolean },
): VideoWorkspaceDraftDirtyState {
  if (!localDraft) {
    return {
      spectrum: false,
      background: false,
      logo: false,
      particles: false,
      text: false,
    }
  }

  if (!persistedDraft) {
    const localSlices = buildVideoWorkspaceDraftSlices(localDraft)
    return {
      spectrum: options?.spectrumDirty ?? Boolean(serializeSlice(localSlices.spectrum)),
      background: Boolean(serializeSlice(localSlices.background)),
      logo: Boolean(serializeSlice(localSlices.logo)),
      particles: Boolean(serializeSlice(localSlices.particles)),
      text: Boolean(serializeSlice(localSlices.text)),
    }
  }

  const localSlices = buildVideoWorkspaceDraftSlices(localDraft)
  const persistedSlices = buildVideoWorkspaceDraftSlices(persistedDraft)

  return {
    spectrum: options?.spectrumDirty ?? serializeSlice(localSlices.spectrum) !== serializeSlice(persistedSlices.spectrum),
    background: serializeSlice(localSlices.background) !== serializeSlice(persistedSlices.background),
    logo: serializeSlice(localSlices.logo) !== serializeSlice(persistedSlices.logo),
    particles: serializeSlice(localSlices.particles) !== serializeSlice(persistedSlices.particles),
    text: serializeSlice(localSlices.text) !== serializeSlice(persistedSlices.text),
  }
}
