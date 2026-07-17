import { normalizeSpectrumPresetKey } from '@/features/video/domains/spectrum/spectrumStyleRegistry'
import { toBoolean, toNumber, toRecord, toStringValue } from '@/features/video/domains/shared/templateValueUtils'

export type SpectrumSettingsState = {
  spectrumEnabled: boolean
  style: string
  audioInputGain: number
  audioBarHeight: number
  audioBandContrast: number
  audioTransientFocus: number
  audioKickImpact: number
  audioBassEmphasis: number
  audioTrebleShimmer: number
  audioPeakHoldBlend: number
  audioMotionSmoothing: number
  flyingGlowWingMotionSpeed: number
  flyingGlowWingRelease: number
  spectrumAttachToLogo: boolean
  spectrumLogoGap: number
  anchor: string
  positionX: number
  positionY: number
}

export function getRecommendedSpectrumLogoGap(logoShape: string, logoSizeStep: number): number {
  const normalizedShape = String(logoShape || '').trim().toLowerCase()
  const safeSizeStep = Math.max(1, Math.min(10, logoSizeStep || 1))
  const baseGap = normalizedShape === 'circle' ? 18 : 28
  const sizeBias = normalizedShape === 'circle' ? safeSizeStep * 1.6 : safeSizeStep * 2.6
  return Number((baseGap + sizeBias).toFixed(1))
}

export function buildSpectrumSettingsState(
  template: Record<string, unknown>,
  logoShape: string,
  logoSizeStep: number,
): SpectrumSettingsState {
  const audioSettings = toRecord(template.audioSettings)
  const position = toRecord(template.position)
  const previewBindings = toRecord(template.previewBindings)

  return {
    spectrumEnabled: toBoolean(template.spectrumEnabled, true),
    style: normalizeSpectrumPresetKey(toStringValue(template.style, 'straight-bars')),
    audioInputGain: toNumber(audioSettings.inputGain, toNumber(audioSettings.sensitivity, 1)),
    audioBarHeight: toNumber(audioSettings.barHeight, 1),
    audioBandContrast: toNumber(audioSettings.bandContrast, toNumber(audioSettings.heightBoost, 1)),
    audioTransientFocus: toNumber(audioSettings.transientFocus, 1),
    audioKickImpact: toNumber(audioSettings.kickImpact, toNumber(audioSettings.kickDrop, 0)),
    audioBassEmphasis: toNumber(audioSettings.bassEmphasis, 1),
    audioTrebleShimmer: toNumber(audioSettings.trebleShimmer, 1),
    audioPeakHoldBlend: toNumber(audioSettings.peakHoldBlend, 0),
    audioMotionSmoothing: toNumber(audioSettings.motionSmoothing, toNumber(audioSettings.smoothing, 0.8)),
    flyingGlowWingMotionSpeed: toNumber(audioSettings.flyingGlowWingMotionSpeed, toNumber(audioSettings.wingMotionSpeed, 1)),
    flyingGlowWingRelease: toNumber(audioSettings.flyingGlowWingRelease, toNumber(audioSettings.wingRelease, 0.9)),
    spectrumAttachToLogo: toBoolean(previewBindings.spectrumAttachToLogo, false),
    spectrumLogoGap: toNumber(previewBindings.spectrumLogoGap, getRecommendedSpectrumLogoGap(logoShape, logoSizeStep)),
    anchor: toStringValue(position.anchor, 'center'),
    positionX: toNumber(position.x, 0),
    positionY: toNumber(position.y, 0),
  }
}

export function buildSpectrumTemplatePatch(
  template: Record<string, unknown>,
  draft: SpectrumSettingsState,
): Record<string, unknown> {
  const currentAudioSettings = toRecord(template.audioSettings)
  const currentPosition = toRecord(template.position)
  const {
    sensitivity: _legacySensitivity,
    heightBoost: _legacyHeightBoost,
    kickDrop: _legacyKickDrop,
    smoothing: _legacySmoothing,
    wingMotionSpeed: _legacyWingMotionSpeed,
    wingRelease: _legacyWingRelease,
    inputGain: _currentInputGain,
    barHeight: _currentBarHeight,
    bandContrast: _currentBandContrast,
    transientFocus: _currentTransientFocus,
    kickImpact: _currentKickImpact,
    bassEmphasis: _currentBassEmphasis,
    trebleShimmer: _currentTrebleShimmer,
    peakHoldBlend: _currentPeakHoldBlend,
    motionSmoothing: _currentMotionSmoothing,
    flyingGlowWingMotionSpeed: _currentFlyingGlowWingMotionSpeed,
    flyingGlowWingRelease: _currentFlyingGlowWingRelease,
    ...restAudioSettings
  } = currentAudioSettings

  return {
    style: draft.style,
    spectrumEnabled: draft.spectrumEnabled,
    previewBindings: {
      ...toRecord(template.previewBindings),
      spectrumAttachToLogo: draft.spectrumAttachToLogo,
      spectrumLogoGap: draft.spectrumLogoGap,
    },
    audioSettings: {
      ...restAudioSettings,
      inputGain: draft.audioInputGain,
      barHeight: draft.audioBarHeight,
      bandContrast: draft.audioBandContrast,
      transientFocus: draft.audioTransientFocus,
      kickImpact: draft.audioKickImpact,
      bassEmphasis: draft.audioBassEmphasis,
      trebleShimmer: draft.audioTrebleShimmer,
      peakHoldBlend: draft.audioPeakHoldBlend,
      motionSmoothing: draft.audioMotionSmoothing,
      flyingGlowWingMotionSpeed: draft.flyingGlowWingMotionSpeed,
      flyingGlowWingRelease: draft.flyingGlowWingRelease,
    },
    position: {
      ...currentPosition,
      anchor: draft.anchor,
      x: draft.positionX,
      y: draft.positionY,
    },
  }
}
