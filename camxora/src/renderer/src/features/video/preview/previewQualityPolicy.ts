import type { RendererPreviewCapability } from '@/features/video/useRendererVideoPreview'

export type PreviewGpuCapabilityProfile = {
  rendererCapability: RendererPreviewCapability
  webgpuAvailable: boolean
  preferredCanvasFormat: string | null
  isFallbackAdapter: boolean
  maxBufferSize: number
  maxStorageBufferBindingSize: number
  maxTextureDimension2D: number
  maxComputeInvocationsPerWorkgroup: number
  maxComputeWorkgroupSizeX: number
  maxComputeWorkgroupStorageSize: number
  featureFlags: string[]
}

export type PreviewQualityTier = 'compatibility' | 'balanced' | 'performance'
export type PreviewBloomQuality = 'off' | 'reduced' | 'full'
export type PreviewMotionBlurQuality = 'off' | 'reduced' | 'full'

export type PreviewQualityPolicy = {
  tier: PreviewQualityTier
  adaptiveQualityLevel: 0 | 1 | 2
  maxDpr: number
  maxRenderPixels: number
  maxSpectrumBars: number
  maxParticleCount: number
  bloomEnabled: boolean
  bloomQuality: PreviewBloomQuality
  allowMotionBlur: boolean
  motionBlurQuality: PreviewMotionBlurQuality
  targetFrameRate: number
}

type BuildPreviewGpuCapabilityProfileOptions = {
  rendererCapability: RendererPreviewCapability
  preferredCanvasFormat?: string | null
  adapter?: {
    features?: Iterable<string>
    isFallbackAdapter?: boolean
  } | null
  device?: {
    limits?: Record<string, number | undefined>
  } | null
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value))
}

function toFiniteNumber(value: unknown, fallback: number): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback
}

export function buildPreviewGpuCapabilityProfile({
  rendererCapability,
  preferredCanvasFormat = null,
  adapter = null,
  device = null,
}: BuildPreviewGpuCapabilityProfileOptions): PreviewGpuCapabilityProfile {
  const limits = device?.limits ?? {}
  return {
    rendererCapability,
    webgpuAvailable: rendererCapability === 'webgpu',
    preferredCanvasFormat: preferredCanvasFormat || null,
    isFallbackAdapter: Boolean(adapter?.isFallbackAdapter),
    maxBufferSize: toFiniteNumber(limits.maxBufferSize, 0),
    maxStorageBufferBindingSize: toFiniteNumber(limits.maxStorageBufferBindingSize, 0),
    maxTextureDimension2D: toFiniteNumber(limits.maxTextureDimension2D, 0),
    maxComputeInvocationsPerWorkgroup: toFiniteNumber(limits.maxComputeInvocationsPerWorkgroup, 0),
    maxComputeWorkgroupSizeX: toFiniteNumber(limits.maxComputeWorkgroupSizeX, 0),
    maxComputeWorkgroupStorageSize: toFiniteNumber(limits.maxComputeWorkgroupStorageSize, 0),
    featureFlags: adapter?.features ? Array.from(adapter.features).sort() : [],
  }
}

export function resolvePreviewQualityPolicy(
  profile: PreviewGpuCapabilityProfile,
): PreviewQualityPolicy {
  if (!profile.webgpuAvailable) {
    return {
      tier: 'compatibility',
      adaptiveQualityLevel: 0,
      maxDpr: 1,
      maxRenderPixels: 1_250_000,
      maxSpectrumBars: 72,
      maxParticleCount: 160,
      bloomEnabled: false,
      bloomQuality: 'off',
      allowMotionBlur: false,
      motionBlurQuality: 'off',
      targetFrameRate: 60,
    }
  }

  const strongLimits =
    profile.maxStorageBufferBindingSize >= 128 * 1024 * 1024 &&
    profile.maxBufferSize >= 256 * 1024 * 1024 &&
    profile.maxTextureDimension2D >= 8192 &&
    profile.maxComputeInvocationsPerWorkgroup >= 512 &&
    profile.maxComputeWorkgroupSizeX >= 256 &&
    profile.maxComputeWorkgroupStorageSize >= 32 * 1024

  const constrainedLimits =
    profile.isFallbackAdapter ||
    profile.maxStorageBufferBindingSize < 32 * 1024 * 1024 ||
    profile.maxBufferSize < 64 * 1024 * 1024 ||
    profile.maxTextureDimension2D < 4096 ||
    profile.maxComputeInvocationsPerWorkgroup < 256

  if (strongLimits) {
    return {
      tier: 'performance',
      adaptiveQualityLevel: 0,
      maxDpr: 2,
      maxRenderPixels: 3_600_000,
      maxSpectrumBars: 180,
      maxParticleCount: 960,
      bloomEnabled: true,
      bloomQuality: 'full',
      allowMotionBlur: true,
      motionBlurQuality: 'full',
      targetFrameRate: 120,
    }
  }

  if (constrainedLimits) {
    return {
      tier: 'compatibility',
      adaptiveQualityLevel: 0,
      maxDpr: 1.25,
      maxRenderPixels: 1_600_000,
      maxSpectrumBars: 84,
      maxParticleCount: 240,
      bloomEnabled: true,
      bloomQuality: 'full',
      allowMotionBlur: false,
      motionBlurQuality: 'off',
      targetFrameRate: 60,
    }
  }

  return {
    tier: 'balanced',
    adaptiveQualityLevel: 0,
    maxDpr: 1.5,
    maxRenderPixels: 2_200_000,
    maxSpectrumBars: 140,
    maxParticleCount: 480,
    bloomEnabled: true,
    bloomQuality: 'full',
    allowMotionBlur: false,
    motionBlurQuality: 'off',
    targetFrameRate: 60,
  }
}

export function clampPreviewDpr(
  baseDpr: number,
  logicalWidth: number,
  logicalHeight: number,
  policy: PreviewQualityPolicy,
): number {
  const safeBaseDpr = clamp(toFiniteNumber(baseDpr, 1), 0.5, Math.max(0.5, policy.maxDpr))
  const basePixels = Math.max(1, logicalWidth * logicalHeight * safeBaseDpr * safeBaseDpr)
  const previewScale = Math.min(1, Math.sqrt(policy.maxRenderPixels / basePixels))
  return clamp(safeBaseDpr * previewScale, 0.5, policy.maxDpr)
}

export function clampPreviewSpectrumBarCount(
  count: number,
  policy: PreviewQualityPolicy,
): number {
  const safeCount = Math.max(0, Math.round(toFiniteNumber(count, 0)))
  return Math.max(24, Math.min(policy.maxSpectrumBars, safeCount))
}

export function clampPreviewParticleCount(
  count: number,
  policy: PreviewQualityPolicy,
): number {
  const safeCount = Math.max(0, Math.round(toFiniteNumber(count, 0)))
  return Math.min(policy.maxParticleCount, safeCount)
}
