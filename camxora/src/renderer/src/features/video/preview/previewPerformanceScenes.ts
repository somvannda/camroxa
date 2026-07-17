import type { PreviewSceneDraft } from '@/features/video/core/contracts/previewDraftContracts'
import type { SpectrumLayerPreview } from '@/features/video/domains/spectrum/spectrumLayerModel'
import type { PreviewQualityPolicy } from '@/features/video/preview/previewQualityPolicy'

export type PreviewPerformanceSceneId =
  | 'baseline'
  | 'max-layers'
  | 'heavy-bloom'
  | 'high-particles'
  | 'text-overlay-pressure'

export type PreviewPerformanceSceneDefinition = {
  id: PreviewPerformanceSceneId
  label: string
  description: string
}

export type PreviewPerformanceNode = {
  primaryScene: PreviewPerformanceSceneId
  activeScenes: PreviewPerformanceSceneId[]
  particleBudget: number
  spectrumLayerCount: number
  spectrumBarCount: number
  textOverlayCount: number
  maxGlow: number
  maxBlur: number
}

type ResolvePreviewPerformanceNodeOptions = {
  draft: PreviewSceneDraft
  enabledTextOverlayCount: number
  qualityPolicy: PreviewQualityPolicy
  spectrumBarCount: number
  spectrumLayers: ReadonlyArray<SpectrumLayerPreview>
}

export const PREVIEW_PERFORMANCE_SCENE_DEFINITIONS: Record<
  PreviewPerformanceSceneId,
  PreviewPerformanceSceneDefinition
> = {
  baseline: {
    id: 'baseline',
    label: 'Baseline',
    description: 'General preview load with no single dominant stressor.',
  },
  'max-layers': {
    id: 'max-layers',
    label: 'Max Layers',
    description: 'High layer count plus dense spectrum bars and atmosphere pressure.',
  },
  'heavy-bloom': {
    id: 'heavy-bloom',
    label: 'Heavy Bloom',
    description: 'Luminous spectrum styling with elevated glow and blur pressure.',
  },
  'high-particles': {
    id: 'high-particles',
    label: 'High Particles',
    description: 'Large particle ceiling intended to stress GPU simulation and blending.',
  },
  'text-overlay-pressure': {
    id: 'text-overlay-pressure',
    label: 'Text Overlay Pressure',
    description: 'Multiple active text overlays layered over the compositor output.',
  },
}

function scoreScenePriority(id: PreviewPerformanceSceneId): number {
  switch (id) {
    case 'max-layers':
      return 4
    case 'heavy-bloom':
      return 3
    case 'high-particles':
      return 2
    case 'text-overlay-pressure':
      return 1
    default:
      return 0
  }
}

function resolvePrimaryScene(
  activeScenes: ReadonlyArray<PreviewPerformanceSceneId>,
): PreviewPerformanceSceneId {
  if (activeScenes.length <= 0) {
    return 'baseline'
  }

  return [...activeScenes].sort((left, right) => scoreScenePriority(right) - scoreScenePriority(left))[0]
}

export function resolvePreviewPerformanceNode({
  draft,
  enabledTextOverlayCount,
  qualityPolicy,
  spectrumBarCount,
  spectrumLayers,
}: ResolvePreviewPerformanceNodeOptions): PreviewPerformanceNode {
  let maxGlow = 0
  let maxBlur = 0
  let totalGlow = 0

  for (const layer of spectrumLayers) {
    const glow = Number(layer.glow) || 0
    const blur = Number(layer.blur) || 0
    maxGlow = Math.max(maxGlow, glow)
    maxBlur = Math.max(maxBlur, blur)
    totalGlow += glow
  }

  const particleBudget = draft.particlesEnabled
    ? Math.max(0, Math.min(draft.particlesMaxCount, qualityPolicy.maxParticleCount))
    : 0
  const denseBars = spectrumBarCount >= Math.max(96, Math.round(qualityPolicy.maxSpectrumBars * 0.78))
  const layeredSpectrum = spectrumLayers.length >= 4 || (spectrumLayers.length >= 3 && denseBars)
  const luminousStyle =
    maxGlow >= 60 ||
    maxBlur >= 12 ||
    totalGlow >= 180 ||
    ['flying-glow', 'halo-stack', 'wave-ribbon', 'liquid-mass'].includes(
      String(draft.style || '').trim().toLowerCase(),
    )
  const highParticles = particleBudget >= Math.max(360, Math.round(qualityPolicy.maxParticleCount * 0.72))
  const textOverlayPressure = enabledTextOverlayCount >= 3

  const activeScenes: PreviewPerformanceSceneId[] = []

  if (layeredSpectrum && (draft.smokeEnabled || draft.vignetteEnabled || denseBars)) {
    activeScenes.push('max-layers')
  }
  if (draft.spectrumEnabled && luminousStyle) {
    activeScenes.push('heavy-bloom')
  }
  if (highParticles) {
    activeScenes.push('high-particles')
  }
  if (textOverlayPressure) {
    activeScenes.push('text-overlay-pressure')
  }

  return {
    primaryScene: resolvePrimaryScene(activeScenes),
    activeScenes,
    particleBudget,
    spectrumLayerCount: spectrumLayers.length,
    spectrumBarCount,
    textOverlayCount: enabledTextOverlayCount,
    maxGlow,
    maxBlur,
  }
}
