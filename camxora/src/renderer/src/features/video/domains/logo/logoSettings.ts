import type { VideoWorkspaceState } from '@/shared/types/desktop'
import { toBoolean, toNumber, toRecord, toStringValue } from '@/features/video/domains/shared/templateValueUtils'

export const LOGO_SPIN_DIRECTION_OPTIONS = [
  { value: 'cw', label: 'Clockwise' },
  { value: 'ccw', label: 'Counter-clockwise' },
] as const

export const LOGO_SHAPE_OPTIONS = [
  { value: 'circle', label: 'Circle Crop' },
  { value: 'square', label: 'Original Image' },
] as const

export const LOGO_MOTION_OPTIONS = [
  { value: 'none', label: 'None' },
  { value: 'zoom', label: 'Zoom' },
  { value: 'vibrate', label: 'Vibrate' },
  { value: 'both', label: 'Zoom + Vibrate' },
] as const

export type LogoSettingsState = {
  logoEnabled: boolean
  logoSpinEnabled: boolean
  logoSpinDirection: string
  logoSpinSpeed: number
  logoPath: string
  logoShape: string
  logoSizeStep: number
  logoOpacity: number
  logoReactivity: number
  logoSmoothing: number
  logoMotionMode: string
  logoMotionZoomStrength: number
  logoMotionVibrateStrength: number
  logoMotionSpeed: number
}

function logoRealSizeToSliderValue(realSize: number): number {
  return Math.max(1, Math.min(10, Number((realSize / 100).toFixed(2))))
}

export function buildLogoSettingsState(
  template: Record<string, unknown>,
  workspace: { logoPath: string } | Pick<VideoWorkspaceState, 'logoPath'>,
): LogoSettingsState {
  const logoSettings = toRecord(template.logoSettings)
  const logoShape = toBoolean(logoSettings.circleMask, true) ? 'circle' : 'square'

  return {
    logoEnabled: toBoolean(logoSettings.enabled, true),
    logoSpinEnabled: toBoolean(logoSettings.spinEnabled, false),
    logoSpinDirection: toStringValue(logoSettings.spinDirection, 'cw'),
    logoSpinSpeed: toNumber(logoSettings.spinSpeed, 0),
    logoPath: toStringValue(workspace.logoPath, toStringValue(template.logoPath, '')),
    logoShape,
    logoSizeStep: logoRealSizeToSliderValue(toNumber(logoSettings.size, 200)),
    logoOpacity: toNumber(logoSettings.opacity, 1),
    logoReactivity: toNumber(logoSettings.reactivity, 0),
    logoSmoothing: toNumber(logoSettings.smoothing, 0.75),
    logoMotionMode: toStringValue(logoSettings.motionMode, 'none'),
    logoMotionZoomStrength: toNumber(logoSettings.motionZoomStrength, 1),
    logoMotionVibrateStrength: toNumber(logoSettings.motionVibrateStrength, 1),
    logoMotionSpeed: toNumber(logoSettings.motionSpeed, 1),
  }
}

export function buildLogoTemplatePatch(
  template: Record<string, unknown>,
  draft: LogoSettingsState,
): Record<string, unknown> {
  const currentLogoSettings = toRecord(template.logoSettings)

  return {
    logoPath: draft.logoPath.trim(),
    previewLogo: draft.logoPath.trim(),
    logoSettings: {
      ...currentLogoSettings,
      enabled: draft.logoEnabled,
      spinEnabled: draft.logoSpinEnabled,
      spinDirection: draft.logoSpinDirection,
      spinSpeed: draft.logoSpinSpeed,
      circleMask: draft.logoShape === 'circle',
      size: Number((draft.logoSizeStep * 100).toFixed(2)),
      opacity: draft.logoOpacity,
      reactivity: draft.logoReactivity,
      smoothing: draft.logoSmoothing,
      motionMode: draft.logoMotionMode,
      motionZoomStrength: draft.logoMotionZoomStrength,
      motionVibrateStrength: draft.logoMotionVibrateStrength,
      motionSpeed: draft.logoMotionSpeed,
    },
  }
}
