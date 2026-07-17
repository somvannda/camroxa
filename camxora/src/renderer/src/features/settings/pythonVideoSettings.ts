export {
  SPECTRUM_PRESET_OPTIONS,
  SPECTRUM_PRESET_RECIPES,
  SPECTRUM_STYLE_OPTIONS,
  SPECTRUM_STYLE_PATCHES,
  STACKED_LAYER_PRESETS,
  STACKED_PRESET_OPTIONS,
  applySpectrumStylePreset,
  buildClearedStackedTemplate,
  buildSpectrumPresetTemplate,
  buildStackedPresetTemplate,
  normalizeSpectrumPresetKey,
} from '@/features/video/domains/spectrum/spectrumStyleRegistry'

export const ANCHOR_OPTIONS = [
  { value: 'top-left', label: 'Top Left' },
  { value: 'top-center', label: 'Top Center' },
  { value: 'top-right', label: 'Top Right' },
  { value: 'center', label: 'Center' },
  { value: 'bottom-left', label: 'Bottom Left' },
  { value: 'bottom-center', label: 'Bottom Center' },
  { value: 'bottom-right', label: 'Bottom Right' },
] as const

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

export const LOGO_SPIN_DIRECTION_OPTIONS = [
  { value: 'cw', label: 'Clockwise' },
  { value: 'ccw', label: 'Counter-clockwise' },
] as const

export const LOGO_SHAPE_OPTIONS = [
  { value: 'circle', label: 'Circle Crop' },
  { value: 'square', label: 'Original Image' },
] as const

export const PARTICLE_SPAWN_MODE_OPTIONS = [
  { value: 'always', label: 'Always' },
  { value: 'reactiveOnly', label: 'Audio Reactive Only' },
] as const

export const PARTICLE_SPAWN_TRIGGER_OPTIONS = [
  { value: 'both', label: 'Kick or Bass' },
  { value: 'kick', label: 'Kick' },
  { value: 'bass', label: 'Bass' },
] as const

export const PARTICLE_VARIANT_OPTIONS = [
  { value: 'classic', label: 'Classic' },
  { value: 'bokeh', label: 'Bokeh Bubbles' },
  { value: 'soap', label: 'Soap Bubble' },
  { value: 'dust', label: 'Floating Dust' },
] as const

export const PARTICLE_SPAWN_AREA_OPTIONS = [
  { value: 'centerRing', label: 'Halo Around Core' },
  { value: 'screenCenter', label: 'Screen Center' },
  { value: 'screenRandom', label: 'Random Screen' },
  { value: 'bottom', label: 'Bottom Arc' },
  { value: 'edges', label: 'Frame Edges' },
  { value: 'full', label: 'Wide Halo Field' },
] as const

export const PARTICLE_STYLE_OPTIONS = [
  { value: 'dot', label: 'Dot' },
  { value: 'glow', label: 'Soft Glow' },
  { value: 'ring', label: 'Ring' },
  { value: 'spark', label: 'Spark' },
  { value: 'bokeh', label: 'Bokeh' },
] as const

export const TEXT_ANIMATION_OPTIONS = [
  { value: 'fade', label: 'Fade' },
  { value: 'slide_up', label: 'Slide Up' },
  { value: 'slide_down', label: 'Slide Down' },
  { value: 'slide_left', label: 'Slide Left' },
  { value: 'slide_right', label: 'Slide Right' },
  { value: 'pop', label: 'Pop' },
  { value: 'typewriter', label: 'Typewriter' },
  { value: 'glow', label: 'Glow Pulse' },
  { value: 'shake', label: 'Shake' },
  { value: 'none', label: 'None' },
] as const
