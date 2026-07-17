import type { PreviewGpuPostFxDraft } from '@/features/video/core/contracts/previewDraftContracts'
import {
  buildPreviewGpuBloomPass,
  computeSpectrumBloomStats,
  type PreviewGpuBloomPass,
} from '@/features/video/preview/previewGpuBloomTuning'
import type { PreviewQualityPolicy, PreviewQualityTier } from '@/features/video/preview/previewQualityPolicy'
import type { SpectrumLayerPreview } from '@/features/video/domains/spectrum/spectrumLayerModel'
import type { WebGpuPostFxSettings } from '@/features/video/webgpu/webgpuSpectrumRenderer'

export type PreviewGpuMotionBlurPass = {
  enabled: boolean
  mode: 'temporal-history'
  sampleCount: number
  shutterAngle: number
  strength: number
}

export type PreviewGpuColorGradePass = {
  enabled: boolean
  exposure: number
  contrast: number
  saturation: number
}

export type PreviewGpuCompositePass = {
  enabled: boolean
  blendMode: 'screen' | 'additive'
  reactiveBoost: number
}

export type PreviewGpuPostFxPlan = {
  enabled: boolean
  qualityTier: PreviewQualityTier
  bloom: PreviewGpuBloomPass | null
  motionBlur: PreviewGpuMotionBlurPass
  colorGrade: PreviewGpuColorGradePass
  composite: PreviewGpuCompositePass
}

type BuildPreviewGpuPostFxPlanOptions = {
  qualityPolicy: PreviewQualityPolicy
  reactiveEnergy: number
  spectrumLayers: ReadonlyArray<SpectrumLayerPreview>
  templateDraft: PreviewGpuPostFxDraft
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value))
}

export function buildPreviewGpuPostFxPlan({
  qualityPolicy,
  reactiveEnergy,
  spectrumLayers,
  templateDraft,
}: BuildPreviewGpuPostFxPlanOptions): PreviewGpuPostFxPlan | null {
  const normalizedStyle = String(templateDraft.style || '').trim().toLowerCase()
  const preserveSharpSpectrumEdges = normalizedStyle === 'flying-glow'
  const bloom = qualityPolicy.bloomEnabled && !preserveSharpSpectrumEdges
    ? buildPreviewGpuBloomPass(
        templateDraft,
        computeSpectrumBloomStats(spectrumLayers),
        reactiveEnergy,
      )
    : null

  const motionBlur: PreviewGpuMotionBlurPass = {
    enabled: qualityPolicy.allowMotionBlur && !preserveSharpSpectrumEdges,
    mode: 'temporal-history',
    sampleCount:
      qualityPolicy.allowMotionBlur && !preserveSharpSpectrumEdges
        ? qualityPolicy.tier === 'performance'
          ? 10
          : 6
        : 0,
    shutterAngle: qualityPolicy.allowMotionBlur && !preserveSharpSpectrumEdges ? 210 : 0,
    strength:
      qualityPolicy.allowMotionBlur && !preserveSharpSpectrumEdges
        ? clamp(0.16 + reactiveEnergy * 0.12, 0.12, 0.32)
        : 0,
  }

  const colorGrade: PreviewGpuColorGradePass = {
    enabled: false,
    exposure: 1,
    contrast: 1,
    saturation: 1,
  }

  const composite: PreviewGpuCompositePass = {
    enabled: Boolean(bloom),
    blendMode: normalizedStyle === 'straight-bars' ? 'screen' : 'additive',
    reactiveBoost: clamp(0.08 + reactiveEnergy * 0.22, 0.08, 0.3),
  }

  if (!bloom && !motionBlur.enabled && !colorGrade.enabled) {
    return null
  }

  return {
    enabled: true,
    qualityTier: qualityPolicy.tier,
    bloom,
    motionBlur,
    colorGrade,
    composite,
  }
}

export function mapPreviewGpuPostFxPlanToWebGpuSettings(
  plan: PreviewGpuPostFxPlan | null,
): WebGpuPostFxSettings | null {
  if (!plan?.enabled || !plan.bloom?.enabled) {
    return null
  }

  return {
    enabled: true,
    threshold: plan.bloom.threshold,
    knee: plan.bloom.knee,
    intensity: plan.bloom.intensity,
    bloomStrength: plan.bloom.bloomStrength,
    blurScale: plan.bloom.blurScale,
    motionBlurStrength: plan.motionBlur.enabled ? plan.motionBlur.strength : 0,
    motionBlurShutterAngle: plan.motionBlur.enabled ? plan.motionBlur.shutterAngle : 0,
    motionBlurSamples: plan.motionBlur.enabled ? plan.motionBlur.sampleCount : 0,
  }
}
