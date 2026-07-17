import type { PreviewGpuPostFxDraft } from '@/features/video/core/contracts/previewDraftContracts'
import { clamp } from '@/features/video/preview/previewUtils'

export type SpectrumLayerBloomStats = {
  maxGlow: number
  maxBlur: number
  luminousLayers: number
  flyingGlowLayers: number
  straightBarsLayers: number
  waveRibbonLayers: number
  liquidMassLayers: number
  haloStackLayers: number
}

export type PreviewGpuBloomPass = {
  enabled: boolean
  threshold: number
  knee: number
  intensity: number
  bloomStrength: number
  blurScale: number
}

export function computeSpectrumBloomStats(
  layers: ArrayLike<{ glow: number; blur: number; blendMode?: string; styleKey?: string }>,
): SpectrumLayerBloomStats {
  const safeLength = Math.max(0, layers.length)
  let maxGlow = 0
  let maxBlur = 0
  let luminousLayers = 0
  let flyingGlowLayers = 0
  let straightBarsLayers = 0
  let waveRibbonLayers = 0
  let liquidMassLayers = 0
  let haloStackLayers = 0
  for (let index = 0; index < safeLength; index += 1) {
    const layer = layers[index]
    if (!layer) {
      continue
    }
    maxGlow = Math.max(maxGlow, Number(layer.glow) || 0)
    maxBlur = Math.max(maxBlur, Number(layer.blur) || 0)
    const blendMode = String(layer.blendMode || 'normal').trim().toLowerCase()
    const styleKey = String(layer.styleKey || '').trim().toLowerCase()
    if (blendMode === 'screen' || blendMode === 'add') {
      luminousLayers += 1
    }
    if (styleKey === 'flying-glow') {
      flyingGlowLayers += 1
    } else if (styleKey === 'straight-bars') {
      straightBarsLayers += 1
    } else if (styleKey === 'wave-ribbon') {
      waveRibbonLayers += 1
    } else if (styleKey === 'liquid-mass') {
      liquidMassLayers += 1
    } else if (styleKey === 'halo-stack') {
      haloStackLayers += 1
    }
  }
  return {
    maxGlow,
    maxBlur,
    luminousLayers,
    flyingGlowLayers,
    straightBarsLayers,
    waveRibbonLayers,
    liquidMassLayers,
    haloStackLayers,
  }
}

export function buildPreviewGpuBloomPass(
  draft: PreviewGpuPostFxDraft,
  bloomStats: SpectrumLayerBloomStats,
  reactiveEnergy: number,
): PreviewGpuBloomPass | null {
  const normalizedStyle = String(draft.style || '').trim().toLowerCase()
  const energy = clamp(reactiveEnergy, 0, 1)
  const glowNorm = clamp(bloomStats.maxGlow / 100, 0, 1.5)
  const blurNorm = clamp(bloomStats.maxBlur / 30, 0, 1.5)
  const luminousNorm = clamp(bloomStats.luminousLayers / 3, 0, 1)
  const flyingGlowNorm =
    normalizedStyle === 'flying-glow' ? 1 : clamp(bloomStats.flyingGlowLayers, 0, 1)
  const straightNorm = clamp(bloomStats.straightBarsLayers, 0, 1)
  const waveNorm = clamp(bloomStats.waveRibbonLayers, 0, 1)
  const liquidNorm = clamp(bloomStats.liquidMassLayers, 0, 1)
  const haloNorm = clamp(bloomStats.haloStackLayers, 0, 1)

  const threshold = clamp(
    0.7 -
      glowNorm * 0.12 -
      energy * 0.04 -
      luminousNorm * 0.05 -
      flyingGlowNorm * 0.05 -
      straightNorm * 0.04 -
      waveNorm * 0.03 -
      haloNorm * 0.06,
    0.4,
    0.84,
  )
  const knee = clamp(
    0.22 +
      glowNorm * 0.16 +
      blurNorm * 0.1 -
      flyingGlowNorm * 0.08 -
      straightNorm * 0.04 +
      waveNorm * 0.06 +
      haloNorm * 0.08,
    0.08,
    0.78,
  )
  const intensity = clamp(
    0.82 +
      glowNorm * 0.46 +
      luminousNorm * 0.18 -
      flyingGlowNorm * 0.08 -
      straightNorm * 0.06 +
      haloNorm * 0.12,
    0.55,
    2.2,
  )
  const bloomStrength = clamp(
    0.2 +
      glowNorm * 0.36 +
      energy * 0.12 +
      luminousNorm * 0.14 +
      flyingGlowNorm * -0.16 +
      straightNorm * 0.02 +
      haloNorm * 0.12 +
      waveNorm * 0.05,
    0,
    1.25,
  )
  const blurScale = clamp(
    0.78 +
      blurNorm * 0.52 +
      glowNorm * 0.12 -
      flyingGlowNorm * 0.22 -
      straightNorm * 0.12 +
      waveNorm * 0.12 +
      liquidNorm * 0.08 +
      haloNorm * 0.1,
    0.45,
    2.1,
  )

  if (!draft.particlesEnabled && glowNorm <= 0.02) {
    return null
  }

  return {
    enabled: true,
    threshold,
    knee,
    intensity,
    bloomStrength,
    blurScale,
  }
}
