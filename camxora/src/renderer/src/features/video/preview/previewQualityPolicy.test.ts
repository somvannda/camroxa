import {
  buildPreviewGpuCapabilityProfile,
  clampPreviewDpr,
  clampPreviewParticleCount,
  clampPreviewSpectrumBarCount,
  resolvePreviewQualityPolicy,
} from '@/features/video/preview/previewQualityPolicy'

describe('previewQualityPolicy', () => {
  it('builds a constrained compatibility policy for non-webgpu capability', () => {
    const profile = buildPreviewGpuCapabilityProfile({
      rendererCapability: 'css',
    })

    expect(resolvePreviewQualityPolicy(profile)).toEqual({
      tier: 'compatibility',
      adaptiveQualityLevel: 0,
      maxDpr: 1,
      maxRenderPixels: 1250000,
      maxSpectrumBars: 72,
      maxParticleCount: 160,
      bloomEnabled: false,
      bloomQuality: 'off',
      allowMotionBlur: false,
      motionBlurQuality: 'off',
      targetFrameRate: 60,
    })
  })

  it('promotes strong adapters into the performance tier', () => {
    const profile = buildPreviewGpuCapabilityProfile({
      rendererCapability: 'webgpu',
      preferredCanvasFormat: 'bgra8unorm',
      adapter: {
        features: ['bgra8unorm-storage'],
      },
      device: {
        limits: {
          maxBufferSize: 512 * 1024 * 1024,
          maxStorageBufferBindingSize: 256 * 1024 * 1024,
          maxTextureDimension2D: 8192,
          maxComputeInvocationsPerWorkgroup: 512,
          maxComputeWorkgroupSizeX: 256,
          maxComputeWorkgroupStorageSize: 32768,
        },
      },
    })

    expect(resolvePreviewQualityPolicy(profile).tier).toBe('performance')
  })

  it('centralizes dpr, bar-count, and particle-count clamps under the policy', () => {
    const policy = {
      tier: 'balanced',
      adaptiveQualityLevel: 0,
      maxDpr: 1.5,
      maxRenderPixels: 2200000,
      maxSpectrumBars: 140,
      maxParticleCount: 480,
      bloomEnabled: true,
      bloomQuality: 'full',
      allowMotionBlur: false,
      motionBlurQuality: 'off',
      targetFrameRate: 60,
    } as const

    expect(clampPreviewDpr(2, 2560, 1440, policy)).toBeLessThanOrEqual(1.5)
    expect(clampPreviewSpectrumBarCount(220, policy)).toBe(140)
    expect(clampPreviewParticleCount(900, policy)).toBe(480)
  })
})
