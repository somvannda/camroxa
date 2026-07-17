import type { PreviewFrameTelemetryReport } from '@/features/video/preview/previewFrameTelemetry'
import type { PreviewPerformanceSceneId } from '@/features/video/preview/previewPerformanceScenes'
import type { PreviewQualityPolicy, PreviewQualityTier } from '@/features/video/preview/previewQualityPolicy'

export type PreviewPerformanceVerificationStatus =
  | 'meeting-target'
  | 'near-target'
  | 'missing-target'

export type PreviewPerformanceVerification = {
  status: PreviewPerformanceVerificationStatus
  summary: string
  targetFrameRate: 60 | 120
  frameBudgetMs: number
  qualityTier: PreviewQualityTier
  adaptiveQualityLevel: 0 | 1 | 2
  performanceScene: PreviewPerformanceSceneId
  usedAdaptiveFallback: boolean
  avgFrameMs: number
  maxFrameMs: number
  renderAvgMs: number
  particlesAvgMs: number
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value))
}

function resolveTargetFrameRate(policy: PreviewQualityPolicy): 60 | 120 {
  return policy.targetFrameRate >= 100 ? 120 : 60
}

function buildSummary(
  status: PreviewPerformanceVerificationStatus,
  targetFrameRate: 60 | 120,
  performanceScene: PreviewPerformanceSceneId,
  usedAdaptiveFallback: boolean,
): string {
  const targetLabel =
    targetFrameRate >= 120 ? '120 FPS high-tier target' : '60 FPS compatibility target'
  const sceneLabel = performanceScene === 'baseline' ? 'baseline scene' : `${performanceScene} stress scene`
  const adaptiveLabel = usedAdaptiveFallback ? ' with adaptive fallback active' : ''

  if (status === 'meeting-target') {
    return `Preview is meeting the ${targetLabel} on the ${sceneLabel}${adaptiveLabel}.`
  }
  if (status === 'near-target') {
    return `Preview is near the ${targetLabel} on the ${sceneLabel}${adaptiveLabel}.`
  }
  return `Preview is missing the ${targetLabel} on the ${sceneLabel}${adaptiveLabel}.`
}

export function evaluatePreviewPerformanceVerification(
  report: PreviewFrameTelemetryReport,
  basePolicy: PreviewQualityPolicy,
): PreviewPerformanceVerification {
  const targetFrameRate = resolveTargetFrameRate(basePolicy)
  const frameBudgetMs = 1000 / targetFrameRate
  const sceneParticlePressure =
    report.performanceScene === 'high-particles' ? frameBudgetMs * 0.42 : frameBudgetMs * 0.5
  const sceneRenderPressure =
    report.performanceScene === 'heavy-bloom' || report.performanceScene === 'max-layers'
      ? frameBudgetMs * 0.82
      : frameBudgetMs * 0.76
  const sceneSpikePressure =
    report.performanceScene === 'baseline' ? frameBudgetMs * 1.42 : frameBudgetMs * 1.56

  let status: PreviewPerformanceVerificationStatus = 'meeting-target'

  if (
    report.avgFrameMs > frameBudgetMs * 1.12 ||
    report.maxFrameMs > frameBudgetMs * 1.82 ||
    report.renderAvgMs > sceneRenderPressure ||
    report.particlesAvgMs > sceneParticlePressure
  ) {
    status = 'missing-target'
  } else if (
    report.avgFrameMs > frameBudgetMs * 1.03 ||
    report.maxFrameMs > sceneSpikePressure ||
    report.renderAvgMs > frameBudgetMs * 0.68 ||
    report.particlesAvgMs > frameBudgetMs * 0.3
  ) {
    status = 'near-target'
  }

  const usedAdaptiveFallback = report.adaptiveQualityLevel > 0

  return {
    status,
    summary: buildSummary(status, targetFrameRate, report.performanceScene, usedAdaptiveFallback),
    targetFrameRate,
    frameBudgetMs: Number(clamp(frameBudgetMs, 1, 1000).toFixed(2)),
    qualityTier: report.qualityTier,
    adaptiveQualityLevel: report.adaptiveQualityLevel,
    performanceScene: report.performanceScene,
    usedAdaptiveFallback,
    avgFrameMs: report.avgFrameMs,
    maxFrameMs: report.maxFrameMs,
    renderAvgMs: report.renderAvgMs,
    particlesAvgMs: report.particlesAvgMs,
  }
}
