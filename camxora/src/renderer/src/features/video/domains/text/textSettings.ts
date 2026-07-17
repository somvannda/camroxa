import { normalizeColor, toBoolean, toNumber, toRecord, toStringValue } from '@/features/video/domains/shared/templateValueUtils'

export type TemplateTextOverlayDraft = {
  enabled: boolean
  text: string
  startSec: number
  durationSec: number
  anchor: string
  x: number
  y: number
  fontSize: number
  color: string
  strokeColor: string
  strokeWidth: number
  shadow: number
  animation: string
}

export type TextSettingsState = {
  textOverlays: TemplateTextOverlayDraft[]
}

export function buildDefaultTextOverlayDraft(): TemplateTextOverlayDraft {
  return {
    enabled: false,
    text: '',
    startSec: 0,
    durationSec: 3,
    anchor: 'center',
    x: 24,
    y: 24,
    fontSize: 46,
    color: '#ffffff',
    strokeColor: '#000000',
    strokeWidth: 2,
    shadow: 0.4,
    animation: 'fade',
  }
}

export function buildTextSettingsState(template: Record<string, unknown>): TextSettingsState {
  const textOverlaysRaw = Array.isArray(template.textOverlays) ? template.textOverlays : []
  const textOverlays = textOverlaysRaw.map((raw) => {
    const rawOverlay = toRecord(raw)
    const fallback = buildDefaultTextOverlayDraft()
    const sizePx = toNumber(rawOverlay.sizePx, Number.NaN)
    return {
      enabled: toBoolean(rawOverlay.enabled, fallback.enabled),
      text: toStringValue(rawOverlay.text, fallback.text),
      startSec: toNumber(rawOverlay.startSec, fallback.startSec),
      durationSec: toNumber(rawOverlay.durationSec, fallback.durationSec),
      anchor: toStringValue(rawOverlay.anchor, fallback.anchor),
      x: toNumber(rawOverlay.x, fallback.x),
      y: toNumber(rawOverlay.y, fallback.y),
      fontSize: Number.isFinite(sizePx) ? sizePx : toNumber(rawOverlay.fontSize, fallback.fontSize),
      color: normalizeColor(rawOverlay.color, fallback.color),
      strokeColor: normalizeColor(rawOverlay.strokeColor, fallback.strokeColor),
      strokeWidth: toNumber(rawOverlay.strokeWidth, fallback.strokeWidth),
      shadow: toNumber(rawOverlay.shadow, fallback.shadow),
      animation: toStringValue(rawOverlay.animation, fallback.animation),
    }
  })

  return { textOverlays }
}

export function buildTextTemplatePatch(draft: TextSettingsState): Record<string, unknown> {
  return {
    textOverlays: draft.textOverlays.map((overlay) => ({
      enabled: overlay.enabled,
      text: overlay.text,
      startSec: overlay.startSec,
      durationSec: overlay.durationSec,
      anchor: overlay.anchor,
      x: overlay.x,
      y: overlay.y,
      sizePx: overlay.fontSize,
      color: overlay.color,
      strokeColor: overlay.strokeColor,
      strokeWidth: overlay.strokeWidth,
      shadow: overlay.shadow,
      animation: overlay.animation,
    })),
  }
}
