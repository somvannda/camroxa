import type { PreviewFrameTelemetryReport } from '@/features/video/preview/previewFrameTelemetry'
import type {
  PreviewBloomQuality,
  PreviewMotionBlurQuality,
  PreviewQualityPolicy,
} from '@/features/video/preview/previewQualityPolicy'

export type PreviewAdaptiveQualityLevel = 0 | 1 | 2

export type PreviewAdaptiveQualityState = {
  level: PreviewAdaptiveQualityLevel
  slowReports: number
  healthyReports: number
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value))
}

function roundInt(value: number): number {
  return Math.max(1, Math.round(value))
}

function resolveBloomQuality(
  base: PreviewBloomQuality,
  level: PreviewAdaptiveQualityLevel,
): PreviewBloomQuality {
  if (base === 'off') {
    return 'off'
  }
  if (level >= 2) {
    return 'off'
  }
  if (level === 1) {
    return 'reduced'
  }
  return base
}

function resolveMotionBlurQuality(
  base: PreviewMotionBlurQuality,
  level: PreviewAdaptiveQualityLevel,
): PreviewMotionBlurQuality {
  if (base === 'off') {
    return 'off'
  }
  if (level >= 1) {
    return level >= 2 ? 'off' : 'reduced'
  }
  return base
}

export function createPreviewAdaptiveQualityState(): PreviewAdaptiveQualityState {
  return {
    level: 0,
    slowReports: 0,
    healthyReports: 0,
  }
}

export function resolveAdaptivePreviewQualityPolicy(
  basePolicy: PreviewQualityPolicy,
  level: PreviewAdaptiveQualityLevel,
): PreviewQualityPolicy {
  const safeLevel = clamp(level, 0, 2) as PreviewAdaptiveQualityLevel
  const bloomQuality = resolveBloomQuality(basePolicy.bloomQuality, safeLevel)
  const motionBlurQuality = resolveMotionBlurQuality(basePolicy.motionBlurQuality, safeLevel)
  const dprScale = safeLevel === 0 ? 1 : safeLevel === 1 ? 0.88 : 0.76
  const pixelScale = safeLevel === 0 ? 1 : safeLevel === 1 ? 0.82 : 0.66
  const barScale = safeLevel === 0 ? 1 : safeLevel === 1 ? 0.86 : 0.72
  const particleScale = safeLevel === 0 ? 1 : safeLevel === 1 ? 0.74 : 0.52

  return {
    ...basePolicy,
    adaptiveQualityLevel: safeLevel,
    maxDpr: Number(clamp(basePolicy.maxDpr * dprScale, 0.75, basePolicy.maxDpr).toFixed(2)),
    maxRenderPixels: roundInt(basePolicy.maxRenderPixels * pixelScale),
    maxSpectrumBars: roundInt(Math.max(24, basePolicy.maxSpectrumBars * barScale)),
    maxParticleCount: roundInt(basePolicy.maxParticleCount * particleScale),
    bloomEnabled: basePolicy.bloomEnabled && bloomQuality !== 'off',
    bloomQuality,
    allowMotionBlur: basePolicy.allowMotionBlur && motionBlurQuality !== 'off',
    motionBlurQuality,
  }
}

export function advancePreviewAdaptiveQualityState(
  state: PreviewAdaptiveQualityState,
  report: PreviewFrameTelemetryReport,
  basePolicy: PreviewQualityPolicy,
): PreviewAdaptiveQualityState {
  const frameBudgetMs = 1000 / Math.max(24, basePolicy.targetFrameRate || 60)
  const overloaded =
    report.avgFrameMs > frameBudgetMs * 1.16 ||
    report.maxFrameMs > frameBudgetMs * 1.85 ||
    report.renderAvgMs > frameBudgetMs * 0.66 ||
    report.particlesAvgMs > frameBudgetMs * 0.3
  const healthy =
    report.avgFrameMs < frameBudgetMs * 0.84 &&
    report.maxFrameMs < frameBudgetMs * 1.25 &&
    report.renderAvgMs < frameBudgetMs * 0.56

  if (overloaded) {
    const slowReports = state.slowReports + 1
    if (slowReports >= 2 && state.level < 2) {
      return {
        level: (state.level + 1) as PreviewAdaptiveQualityLevel,
        slowReports: 0,
        healthyReports: 0,
      }
    }
    return {
      level: state.level,
      slowReports,
      healthyReports: 0,
    }
  }

  if (healthy) {
    const healthyReports = state.healthyReports + 1
    if (healthyReports >= 3 && state.level > 0) {
      return {
        level: (state.level - 1) as PreviewAdaptiveQualityLevel,
        slowReports: 0,
        healthyReports: 0,
      }
    }
    return {
      level: state.level,
      slowReports: 0,
      healthyReports,
    }
  }

  return {
    level: state.level,
    slowReports: 0,
    healthyReports: 0,
  }
}
