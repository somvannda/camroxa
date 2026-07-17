import type { TemplateTextOverlayDraft } from '@/features/settings/settingsTemplateDraft'

export function buildTextPresetStyle(preset: string): Partial<TemplateTextOverlayDraft> | null {
  if (preset === 'neon_outline') {
    return {
      fontSize: 72,
      color: '#ffffff',
      strokeColor: '#ff4fd8',
      strokeWidth: 3,
      shadow: 0.45,
      animation: 'pop',
    }
  }
  if (preset === 'soft_glow') {
    return {
      fontSize: 58,
      color: '#dff6ff',
      strokeColor: '#051229',
      strokeWidth: 1.5,
      shadow: 0.6,
      animation: 'fade',
    }
  }
  if (preset === 'dark_stroke') {
    return {
      fontSize: 62,
      color: '#ffffff',
      strokeColor: '#000000',
      strokeWidth: 4,
      shadow: 0.35,
      animation: 'fade',
    }
  }
  return null
}
