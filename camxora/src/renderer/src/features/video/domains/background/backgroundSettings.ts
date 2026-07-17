import { toBoolean, toNumber, toRecord, toStringValue } from '@/features/video/domains/shared/templateValueUtils'

export const BACKGROUND_FIT_OPTIONS = [
  { value: 'cover', label: 'Cover' },
  { value: 'contain', label: 'Contain' },
  { value: 'original', label: 'Original' },
] as const

export const BACKGROUND_MOTION_OPTIONS = [
  { value: 'none', label: 'None' },
  { value: 'zoom', label: 'Zoom' },
  { value: 'vibrate', label: 'Vibrate' },
  { value: 'both', label: 'Zoom + Vibrate' },
] as const

export type BackgroundSettingsState = {
  backgroundEnabled: boolean
  backgroundFitMode: string
  backgroundUserScale: number
  backgroundBrightness: number
  backgroundReactivity: number
  backgroundSmoothing: number
  backgroundMotionMode: string
  backgroundMotionZoomStrength: number
  backgroundMotionVibrateStrength: number
  backgroundMotionSpeed: number
}

export function buildBackgroundSettingsState(template: Record<string, unknown>): BackgroundSettingsState {
  const backgroundSettings = toRecord(template.backgroundSettings)

  return {
    backgroundEnabled: toBoolean(backgroundSettings.enabled, true),
    backgroundFitMode: toStringValue(backgroundSettings.fitMode, 'cover'),
    backgroundUserScale: toNumber(backgroundSettings.userScale, 1),
    backgroundBrightness: toNumber(backgroundSettings.brightness, 1),
    backgroundReactivity: toNumber(backgroundSettings.reactivity, 0),
    backgroundSmoothing: toNumber(backgroundSettings.smoothing, 0.8),
    backgroundMotionMode: toStringValue(backgroundSettings.motionMode, 'none'),
    backgroundMotionZoomStrength: toNumber(backgroundSettings.motionZoomStrength, 1),
    backgroundMotionVibrateStrength: toNumber(backgroundSettings.motionVibrateStrength, 1),
    backgroundMotionSpeed: toNumber(backgroundSettings.motionSpeed, 1),
  }
}

export function buildBackgroundTemplatePatch(
  template: Record<string, unknown>,
  draft: BackgroundSettingsState,
): Record<string, unknown> {
  const currentBackgroundSettings = toRecord(template.backgroundSettings)

  return {
    backgroundSettings: {
      ...currentBackgroundSettings,
      enabled: draft.backgroundEnabled,
      fitMode: draft.backgroundFitMode,
      userScale: draft.backgroundUserScale,
      brightness: draft.backgroundBrightness,
      reactivity: draft.backgroundReactivity,
      smoothing: draft.backgroundSmoothing,
      motionMode: draft.backgroundMotionMode,
      motionZoomStrength: draft.backgroundMotionZoomStrength,
      motionVibrateStrength: draft.backgroundMotionVibrateStrength,
      motionSpeed: draft.backgroundMotionSpeed,
      userOffsetX: toNumber(currentBackgroundSettings.userOffsetX, 0),
      userOffsetY: toNumber(currentBackgroundSettings.userOffsetY, 0),
    },
  }
}
