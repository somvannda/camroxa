type SpectrumPresetRecipe = {
  style: string
  layers: Array<Record<string, unknown>>
}

export const SPECTRUM_STYLE_OPTIONS = [
  { value: 'straight-bars', label: 'Straight Bars' },
  { value: 'flying-glow', label: 'Flying Glow' },
  { value: 'orbital-bars', label: 'Orbital Bars' },
  { value: 'dot-matrix', label: 'Dot Matrix' },
  { value: 'wave-ribbon', label: 'Wave Ribbon' },
  { value: 'liquid-mass', label: 'Liquid Mass' },
  { value: 'halo-stack', label: 'Halo Stack' },
] as const

export const SPECTRUM_STYLE_PATCHES: Record<string, Record<string, unknown>> = {
  'classic-vertical': {
    curved: true,
    mirrored: true,
    fillCircle: false,
    barWidth: 4,
    thickness: 30,
    gravity: 'bottom',
  },
  'thin-lines': {
    curved: true,
    mirrored: true,
    fillCircle: false,
    barWidth: 2,
    thickness: 34,
    gravity: 'bottom',
  },
  'dot-matrix': {
    curved: true,
    mirrored: true,
    fillCircle: false,
    barWidth: 4,
    thickness: 28,
    gravity: 'bottom',
  },
  'symmetrical-bars': {
    curved: true,
    mirrored: true,
    fillCircle: false,
    barWidth: 5,
    thickness: 38,
    gravity: 'bottom',
  },
  'soft-waveform': {
    curved: true,
    mirrored: true,
    fillCircle: false,
    barWidth: 4,
    thickness: 24,
    gravity: 'bottom',
  },
  mountain: {
    curved: true,
    mirrored: true,
    fillCircle: true,
    barWidth: 5,
    thickness: 56,
    gravity: 'bottom',
  },
  liquid: {
    curved: true,
    mirrored: true,
    fillCircle: true,
    barWidth: 9,
    thickness: 38,
    gravity: 'bottom',
  },
  'pixel-bars': {
    curved: true,
    mirrored: true,
    fillCircle: false,
    barWidth: 5,
    thickness: 36,
    gravity: 'bottom',
  },
  'neon-pulse': {
    curved: true,
    mirrored: true,
    fillCircle: false,
    barWidth: 7,
    thickness: 42,
    gravity: 'bottom',
  },
  'floating-blocks': {
    curved: true,
    mirrored: true,
    fillCircle: false,
    barWidth: 6,
    thickness: 34,
    gravity: 'bottom',
  },
  'orbital-bars': {
    curved: true,
    mirrored: true,
    fillCircle: false,
    barWidth: 5.5,
    thickness: 44,
    gravity: 'bottom',
  },
}

export const STACKED_PRESET_OPTIONS = [
  { value: '', label: 'Pick stacked preset...' },
  { value: 'triple-neon-halo', label: 'Triple Neon Halo' },
  { value: 'bass-vortex-stack', label: 'Bass Vortex Stack' },
  { value: 'soft-aura-stack', label: 'Soft Aura Stack' },
] as const

export const STACKED_LAYER_PRESETS: Record<
  string,
  {
    style: string
    layers: Array<Record<string, unknown>>
  }
> = {
  'triple-neon-halo': {
    style: 'neon-pulse',
    layers: [
      {
        name: 'Inner Core',
        radiusOffset: 0,
        barWidth: 10,
        thickness: 26,
        fillCircle: true,
        opacity: 0.95,
        blend_mode: 'normal',
        glow: 24,
        blur: 6,
        color: {
          mode: 'gradient',
          gradientColors: ['#ffffff', '#ffe082'],
          gradientDirection: 'circular',
        },
      },
      {
        name: 'Pulse Ring',
        radiusOffset: 26,
        barWidth: 9,
        thickness: 42,
        fillCircle: false,
        opacity: 0.85,
        blend_mode: 'add',
        glow: 68,
        blur: 14,
        color: {
          mode: 'gradient',
          gradientColors: ['#ff00ff', '#00ffff'],
          gradientDirection: 'circular',
        },
      },
      {
        name: 'Outer Aura',
        radiusOffset: 56,
        barWidth: 8,
        thickness: 30,
        fillCircle: false,
        opacity: 0.72,
        blend_mode: 'screen',
        glow: 82,
        blur: 20,
        color: {
          mode: 'gradient',
          gradientColors: ['#7c3aed', '#38bdf8'],
          gradientDirection: 'circular',
        },
      },
    ],
  },
  'bass-vortex-stack': {
    style: 'liquid',
    layers: [
      {
        name: 'Vortex Fill',
        radiusOffset: 0,
        barWidth: 12,
        thickness: 36,
        fillCircle: true,
        opacity: 0.92,
        blend_mode: 'normal',
        glow: 18,
        blur: 5,
        color: {
          mode: 'gradient',
          gradientColors: ['#ffffff', '#f5f3ff'],
          gradientDirection: 'circular',
        },
      },
      {
        name: 'Energy Ring',
        radiusOffset: 22,
        barWidth: 11,
        thickness: 52,
        fillCircle: false,
        opacity: 0.82,
        blend_mode: 'add',
        glow: 72,
        blur: 16,
        color: {
          mode: 'gradient',
          gradientColors: ['#8b5cf6', '#ec4899'],
          gradientDirection: 'circular',
        },
      },
      {
        name: 'Outer Shock',
        radiusOffset: 52,
        barWidth: 7,
        thickness: 60,
        fillCircle: false,
        opacity: 0.7,
        blend_mode: 'screen',
        glow: 88,
        blur: 22,
        color: {
          mode: 'gradient',
          gradientColors: ['#60a5fa', '#ffffff'],
          gradientDirection: 'radial',
        },
      },
    ],
  },
  'soft-aura-stack': {
    style: 'soft-waveform',
    layers: [
      {
        name: 'Base Halo',
        radiusOffset: 0,
        barWidth: 7,
        thickness: 22,
        fillCircle: false,
        opacity: 0.85,
        blend_mode: 'normal',
        glow: 24,
        blur: 8,
        color: {
          mode: 'gradient',
          gradientColors: ['#c084fc', '#f0abfc'],
          gradientDirection: 'circular',
        },
      },
      {
        name: 'Bright Ribbon',
        radiusOffset: 20,
        barWidth: 5,
        thickness: 28,
        fillCircle: false,
        opacity: 0.72,
        blend_mode: 'screen',
        glow: 58,
        blur: 14,
        color: {
          mode: 'gradient',
          gradientColors: ['#ffffff', '#93c5fd'],
          gradientDirection: 'circular',
        },
      },
      {
        name: 'Outer Mist',
        radiusOffset: 42,
        barWidth: 9,
        thickness: 18,
        fillCircle: false,
        opacity: 0.55,
        blend_mode: 'screen',
        glow: 76,
        blur: 18,
        color: {
          mode: 'gradient',
          gradientColors: ['#38bdf8', '#818cf8'],
          gradientDirection: 'radial',
        },
      },
    ],
  },
}

const SPECTRUM_PRESET_ALIASES: Record<string, string> = {
  'classic-vertical': 'straight-bars',
  'thin-lines': 'straight-bars',
  'symmetrical-bars': 'straight-bars',
  'pixel-bars': 'straight-bars',
  'neon-pulse': 'flying-glow',
  'floating-blocks': 'flying-glow',
  'soft-waveform': 'wave-ribbon',
  mountain: 'liquid-mass',
  liquid: 'liquid-mass',
  'triple-neon-halo': 'halo-stack',
  'bass-vortex-stack': 'halo-stack',
  'soft-aura-stack': 'wave-ribbon',
}

export function normalizeSpectrumPresetKey(presetKey: string): string {
  const normalized = String(presetKey || '').trim().toLowerCase()
  if (!normalized) {
    return 'straight-bars'
  }
  return SPECTRUM_PRESET_ALIASES[normalized] ?? normalized
}

const SIMPLE_SPECTRUM_PRESET_RECIPES: Record<string, SpectrumPresetRecipe> = {
  'straight-bars': {
    style: 'straight-bars',
    layers: [
      {
        name: 'Straight Bars',
        radiusOffset: 0,
        curved: false,
        mirrored: false,
        fillCircle: false,
        gravity: 'bottom',
        barWidth: 1.4,
        thickness: 86,
        opacity: 1,
        glow: 0,
        blur: 0,
        blend_mode: 'normal',
        color: {
          mode: 'gradient',
          gradientColors: ['#5ef3ff', '#44c8ff', '#2f86ff', '#3f55ff', '#6a45ff', '#a33bff', '#ff2fa6', '#ff4a6d'],
          gradientDirection: 'left-to-right',
        },
      },
    ],
  },
  'flying-glow': {
    style: 'flying-glow',
    layers: [
      {
        name: 'Flying Glow',
        radiusOffset: 0,
        curved: true,
        mirrored: true,
        solidBand: true,
        fillCircle: false,
        gravity: 'bottom',
        barWidth: 7,
        thickness: 86,
        opacity: 1,
        glow: 14,
        blur: 0.6,
        blend_mode: 'normal',
        color: {
          mode: 'gradient',
          gradientColors: ['#55e8ff', '#f8fbff', '#9d84ff'],
          gradientDirection: 'left-to-right',
        },
      },
    ],
  },
  'orbital-bars': {
    style: 'orbital-bars',
    layers: [
      {
        name: 'Orbital Bars',
        radiusOffset: 0,
        curved: true,
        mirrored: true,
        fillCircle: false,
        gravity: 'bottom',
        barWidth: 5.5,
        thickness: 58,
        opacity: 0.94,
        glow: 26,
        blur: 5,
        blend_mode: 'screen',
        color: {
          mode: 'gradient',
          gradientColors: ['#5be8ff', '#89a8ff', '#c46dff', '#ff7adf'],
          gradientDirection: 'circular',
        },
      },
    ],
  },
  'dot-matrix': {
    style: 'dot-matrix',
    layers: [
      {
        name: 'Dot Matrix',
        radiusOffset: 0,
        curved: false,
        mirrored: false,
        fillCircle: false,
        gravity: 'bottom',
        barWidth: 4,
        thickness: 46,
        opacity: 0.92,
        glow: 18,
        blur: 4,
        blend_mode: 'normal',
        color: {
          mode: 'gradient',
          gradientColors: ['#ffffff', '#ff78df', '#72d8ff'],
          gradientDirection: 'left-to-right',
        },
      },
    ],
  },
  'wave-ribbon': {
    style: 'wave-ribbon',
    layers: [
      {
        name: 'Wave Ribbon',
        radiusOffset: 0,
        curved: false,
        mirrored: false,
        fillCircle: false,
        gravity: 'bottom',
        barWidth: 6.5,
        thickness: 54,
        opacity: 0.9,
        glow: 18,
        blur: 4,
        blend_mode: 'screen',
        color: {
          mode: 'gradient',
          gradientColors: ['#ffb8f4', '#ffffff', '#9ce7ff'],
          gradientDirection: 'left-to-right',
        },
      },
    ],
  },
  'liquid-mass': {
    style: 'liquid-mass',
    layers: [
      {
        name: 'Liquid Body',
        radiusOffset: 0,
        curved: false,
        mirrored: false,
        fillCircle: false,
        gravity: 'bottom',
        barWidth: 11.5,
        thickness: 92,
        opacity: 0.94,
        glow: 20,
        blur: 4,
        blend_mode: 'normal',
        color: {
          mode: 'gradient',
          gradientColors: ['#fff1f8', '#ff8add', '#8a76ff', '#3cd6ff'],
          gradientDirection: 'left-to-right',
        },
      },
    ],
  },
}

const CURATED_STACKED_SPECTRUM_PRESET_RECIPES: Record<string, SpectrumPresetRecipe> = {
  'halo-stack': {
    style: 'halo-stack',
    layers: [
      {
        name: 'Halo Stack',
        radiusOffset: 0,
        curved: false,
        mirrored: false,
        fillCircle: false,
        gravity: 'bottom',
        barWidth: 9,
        thickness: 94,
        opacity: 0.92,
        glow: 64,
        blur: 10,
        blend_mode: 'screen',
        color: {
          mode: 'gradient',
          gradientColors: ['#fff2b4', '#ff79e5', '#ffffff', '#72eaff'],
          gradientDirection: 'left-to-right',
        },
      },
    ],
  },
}

export const SPECTRUM_PRESET_OPTIONS = [
  { value: 'straight-bars', label: 'Straight Bars' },
  { value: 'flying-glow', label: 'Flying Glow' },
  { value: 'orbital-bars', label: 'Orbital Bars' },
  { value: 'dot-matrix', label: 'Dot Matrix' },
  { value: 'wave-ribbon', label: 'Wave Ribbon' },
  { value: 'liquid-mass', label: 'Liquid Mass' },
  { value: 'halo-stack', label: 'Halo Stack' },
] as const

export const SPECTRUM_PRESET_RECIPES: Record<string, SpectrumPresetRecipe> = {
  ...SIMPLE_SPECTRUM_PRESET_RECIPES,
  ...CURATED_STACKED_SPECTRUM_PRESET_RECIPES,
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

export function applySpectrumStylePreset(
  template: Record<string, unknown>,
  styleKey: string,
): Record<string, unknown> {
  return buildSpectrumPresetTemplate(template, styleKey) ?? buildSpectrumPresetTemplate(template, 'straight-bars') ?? template
}

export function buildStackedPresetTemplate(
  template: Record<string, unknown>,
  presetKey: string,
): Record<string, unknown> | null {
  return buildSpectrumPresetTemplate(template, presetKey)
}

export function buildSpectrumPresetTemplate(
  template: Record<string, unknown>,
  presetKey: string,
): Record<string, unknown> | null {
  const normalizedPresetKey = normalizeSpectrumPresetKey(presetKey)
  const preset = SPECTRUM_PRESET_RECIPES[normalizedPresetKey]
  if (!preset) {
    return null
  }

  const rawLayers = Array.isArray(template.layers) ? template.layers : []
  const fallbackLayer =
    rawLayers.length > 0 && isRecord(rawLayers[0]) ? rawLayers[0] : { color: { mode: 'solid', solidColor: '#ffffff' } }

  const nextLayers = preset.layers.map((layerPatch, index) => {
    const fallbackColor = isRecord(fallbackLayer.color) ? fallbackLayer.color : {}
    const patchColor = isRecord(layerPatch.color) ? layerPatch.color : {}

    return {
      ...fallbackLayer,
      ...layerPatch,
      id: `stack-${presetKey}-${index + 1}`,
      color: {
        ...fallbackColor,
        ...patchColor,
      },
    }
  })

  return {
    ...template,
    style: normalizedPresetKey,
    layers: nextLayers,
  }
}

export function buildClearedStackedTemplate(template: Record<string, unknown>): Record<string, unknown> {
  return buildSpectrumPresetTemplate(template, 'straight-bars') ?? template
}
