import { normalizeColor, toBoolean, toNumber, toRecord } from '@/features/video/domains/shared/templateValueUtils'

export type AtmosphereSettingsState = {
  vignetteEnabled: boolean
  vignetteStrength: number
  vignetteFeather: number
  vignetteOpacity: number
  vignetteColor: string
  smokeEnabled: boolean
  smokeStrength: number
  smokeBlur: number
  smokeNoise: number
  smokeSpeed: number
  smokeOpacity: number
  smokeColor: string
}

export function buildAtmosphereSettingsState(template: Record<string, unknown>): AtmosphereSettingsState {
  const effects = toRecord(template.effects)
  const vignette = toRecord(effects.vignette)
  const smoke = toRecord(effects.smoke)

  return {
    vignetteEnabled: toBoolean(vignette.enabled, false),
    vignetteStrength: toNumber(vignette.strength, 0.35),
    vignetteFeather: toNumber(vignette.feather, 0.65),
    vignetteOpacity: toNumber(vignette.opacity, 0.65),
    vignetteColor: normalizeColor(vignette.color, '#000000'),
    smokeEnabled: toBoolean(smoke.enabled, false),
    smokeStrength: toNumber(smoke.strength, 0.35),
    smokeBlur: toNumber(smoke.blur, 0.55),
    smokeNoise: toNumber(smoke.noise, 0.55),
    smokeSpeed: toNumber(smoke.speed, 0.35),
    smokeOpacity: toNumber(smoke.opacity, 0.55),
    smokeColor: normalizeColor(smoke.color, '#000000'),
  }
}

export function buildAtmosphereTemplatePatch(
  template: Record<string, unknown>,
  draft: AtmosphereSettingsState,
): Record<string, unknown> {
  const currentEffects = toRecord(template.effects)
  const currentVignette = toRecord(currentEffects.vignette)
  const currentSmoke = toRecord(currentEffects.smoke)

  return {
    effects: {
      ...currentEffects,
      vignette: {
        ...currentVignette,
        enabled: draft.vignetteEnabled,
        strength: draft.vignetteStrength,
        feather: draft.vignetteFeather,
        opacity: draft.vignetteOpacity,
        color: draft.vignetteColor,
      },
      smoke: {
        ...currentSmoke,
        enabled: draft.smokeEnabled,
        strength: draft.smokeStrength,
        blur: draft.smokeBlur,
        noise: draft.smokeNoise,
        speed: draft.smokeSpeed,
        opacity: draft.smokeOpacity,
        color: draft.smokeColor,
      },
    },
  }
}
