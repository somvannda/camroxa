import { describe, expect, it } from 'vitest'

import { buildPreviewLifecycleState } from '@/features/video/preview/previewLifecycleState'

describe('buildPreviewLifecycleState', () => {
  it('marks a ready scene with fallback as fallback-active', () => {
    const result = buildPreviewLifecycleState({
      capability: 'webgpu',
      lastError: null,
      scene: {
        viewport: { showFallbackScene: true },
      } as never,
      webgpuStatus: 'ready',
    })

    expect(result.status).toBe('fallback-active')
    expect(result.label).toBe('Fallback Scene Active')
  })

  it('marks device loss as recoverable', () => {
    const result = buildPreviewLifecycleState({
      capability: 'webgpu',
      lastError: 'GPU lost',
      scene: {
        viewport: { showFallbackScene: false },
      } as never,
      webgpuStatus: 'device-lost',
    })

    expect(result.status).toBe('device-lost')
    expect(result.canRecover).toBe(true)
    expect(result.message).toContain('GPU lost')
  })

  it('treats a scene with a live WebGPU viewport as running even during transient initializing status', () => {
    const result = buildPreviewLifecycleState({
      capability: 'webgpu',
      lastError: null,
      scene: {
        viewport: {
          showFallbackScene: false,
          webgpuReady: true,
        },
      } as never,
      webgpuStatus: 'initializing',
    })

    expect(result.status).toBe('running')
    expect(result.label).toBe('Preview Running')
  })
})
