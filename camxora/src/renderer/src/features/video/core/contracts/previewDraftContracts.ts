import type { AtmosphereSettingsState } from '@/features/video/domains/atmosphere/atmosphereSettings'
import type { BackgroundSettingsState } from '@/features/video/domains/background/backgroundSettings'
import type { LogoSettingsState } from '@/features/video/domains/logo/logoSettings'
import type { ParticleSettingsState } from '@/features/video/domains/particles/particleSettings'
import type { SpectrumSettingsState } from '@/features/video/domains/spectrum/spectrumSettings'
import type { TextSettingsState } from '@/features/video/domains/text/textSettings'

export type PreviewDraftSource = SpectrumSettingsState &
  BackgroundSettingsState &
  AtmosphereSettingsState &
  LogoSettingsState &
  ParticleSettingsState

export type PreviewTextDraft = Pick<TextSettingsState, 'textOverlays'>

export type PreviewFramePositionDraft = Pick<
  SpectrumSettingsState,
  'anchor' | 'positionX' | 'positionY'
>

export type PreviewSpectrumBarCountDraft = PreviewFramePositionDraft &
  Pick<SpectrumSettingsState, 'style'>

export type PreviewReactiveFrameDraft = Pick<
  SpectrumSettingsState,
  | 'style'
  | 'audioInputGain'
  | 'audioBarHeight'
  | 'audioBandContrast'
  | 'audioTransientFocus'
  | 'audioKickImpact'
  | 'audioBassEmphasis'
  | 'audioTrebleShimmer'
  | 'audioPeakHoldBlend'
  | 'audioMotionSmoothing'
  | 'flyingGlowWingMotionSpeed'
  | 'flyingGlowWingRelease'
> &
  Pick<BackgroundSettingsState, 'backgroundSmoothing'> &
  Pick<LogoSettingsState, 'logoSmoothing'>

export type PreviewGpuSpectrumDraft = Pick<
  SpectrumSettingsState,
  | 'spectrumEnabled'
  | 'audioInputGain'
  | 'audioBarHeight'
  | 'audioBandContrast'
  | 'audioTransientFocus'
  | 'audioKickImpact'
  | 'audioBassEmphasis'
  | 'audioTrebleShimmer'
  | 'audioPeakHoldBlend'
  | 'audioMotionSmoothing'
  | 'flyingGlowWingMotionSpeed'
  | 'flyingGlowWingRelease'
> &
  Pick<
    LogoSettingsState,
    'logoEnabled' | 'logoPath' | 'logoSizeStep'
  > &
  Pick<
    SpectrumSettingsState,
    'spectrumAttachToLogo' | 'spectrumLogoGap'
  >

export type PreviewParticleRuntimeDraft = ParticleSettingsState

export type PreviewAtmosphereDraft = AtmosphereSettingsState

export type PreviewGpuPostFxDraft = Pick<ParticleSettingsState, 'particlesEnabled'> &
  Pick<SpectrumSettingsState, 'spectrumEnabled' | 'style'>

export type PreviewGpuRuntimeDraft = {
  atmosphere: PreviewAtmosphereDraft
  particles: PreviewParticleRuntimeDraft
  postFx: PreviewGpuPostFxDraft
  spectrum: PreviewGpuSpectrumDraft
}

export type PreviewBackgroundPresentationDraft = BackgroundSettingsState

export type PreviewLogoPresentationDraft = Pick<
  SpectrumSettingsState,
  'anchor' | 'positionX' | 'positionY'
> &
  LogoSettingsState

export type PreviewSpectrumAttachmentDraft = Pick<
  LogoSettingsState,
  'logoEnabled' | 'logoPath' | 'logoSizeStep'
> &
  Pick<SpectrumSettingsState, 'spectrumAttachToLogo' | 'spectrumLogoGap'>

export type LogoSpectrumBindingDraft = LogoSettingsState &
  Pick<SpectrumSettingsState, 'spectrumAttachToLogo' | 'spectrumLogoGap'>

export type PreviewSceneDraft = PreviewDraftSource

export type PreviewDomPresentationDraft = PreviewBackgroundPresentationDraft &
  PreviewLogoPresentationDraft

export type PreviewLogoDrawDraft = Pick<
  LogoSettingsState,
  'logoEnabled' | 'logoShape'
>

export function pickPreviewFramePositionDraft(
  draft: PreviewDraftSource,
): PreviewFramePositionDraft {
  return {
    anchor: draft.anchor,
    positionX: draft.positionX,
    positionY: draft.positionY,
  }
}

export function pickPreviewReactiveFrameDraft(
  draft: PreviewDraftSource,
): PreviewReactiveFrameDraft {
  return {
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
    backgroundSmoothing: draft.backgroundSmoothing,
    logoSmoothing: draft.logoSmoothing,
  }
}

export function pickPreviewGpuRuntimeDraft(
  draft: PreviewDraftSource,
): PreviewGpuRuntimeDraft {
  return {
    atmosphere: {
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
    },
    particles: {
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
    },
    postFx: {
      particlesEnabled: draft.particlesEnabled,
      spectrumEnabled: draft.spectrumEnabled,
      style: draft.style,
    },
    spectrum: {
      spectrumEnabled: draft.spectrumEnabled,
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
      logoEnabled: draft.logoEnabled,
      logoPath: draft.logoPath,
      logoSizeStep: draft.logoSizeStep,
      spectrumAttachToLogo: draft.spectrumAttachToLogo,
      spectrumLogoGap: draft.spectrumLogoGap,
    },
  }
}

export function pickPreviewDomPresentationDraft(
  draft: PreviewDraftSource,
): PreviewDomPresentationDraft {
  return {
    anchor: draft.anchor,
    positionX: draft.positionX,
    positionY: draft.positionY,
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
    backgroundFitMode: draft.backgroundFitMode,
    backgroundUserScale: draft.backgroundUserScale,
    backgroundBrightness: draft.backgroundBrightness,
    backgroundReactivity: draft.backgroundReactivity,
    backgroundSmoothing: draft.backgroundSmoothing,
    backgroundMotionMode: draft.backgroundMotionMode,
    backgroundMotionZoomStrength: draft.backgroundMotionZoomStrength,
    backgroundMotionVibrateStrength: draft.backgroundMotionVibrateStrength,
    backgroundMotionSpeed: draft.backgroundMotionSpeed,
  }
}

export function pickPreviewLogoDrawDraft(
  draft: PreviewDraftSource,
): PreviewLogoDrawDraft {
  return {
    logoEnabled: draft.logoEnabled,
    logoShape: draft.logoShape,
  }
}
