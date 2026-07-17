import type { VideoPreviewScene } from '@/features/video/preview/previewScene'
import type { PreviewSurfaceStatus } from '@/features/video/preview/usePreviewSurfaceLifecycle'
import type { RendererPreviewCapability } from '@/features/video/useRendererVideoPreview'

export type PreviewLifecycleStatus =
  | 'unsupported'
  | 'initializing'
  | 'running'
  | 'recovering'
  | 'device-lost'
  | 'fallback-active'
  | 'error'

export type PreviewLifecycleState = {
  status: PreviewLifecycleStatus
  label: string
  message: string
  capability: RendererPreviewCapability
  webgpuStatus: PreviewSurfaceStatus
  fallbackActive: boolean
  canRecover: boolean
  lastError: string | null
}

type BuildPreviewLifecycleStateOptions<TOverlay> = {
  capability: RendererPreviewCapability
  scene: VideoPreviewScene<TOverlay>
  webgpuStatus: PreviewSurfaceStatus
  lastError: string | null
}

export function buildPreviewLifecycleState<TOverlay>({
  capability,
  scene,
  webgpuStatus,
  lastError,
}: BuildPreviewLifecycleStateOptions<TOverlay>): PreviewLifecycleState {
  const fallbackActive = scene.viewport.showFallbackScene
  const sceneWebGpuReady = scene.viewport.webgpuReady === true

  if (capability !== 'webgpu' || webgpuStatus === 'unsupported') {
    return {
      status: 'unsupported',
      label: 'WebGPU Unsupported',
      message:
        'This machine does not currently expose WebGPU to the Electron renderer, so the live GPU compositor cannot start in this session.',
      capability,
      webgpuStatus,
      fallbackActive: false,
      canRecover: false,
      lastError,
    }
  }

  if (webgpuStatus === 'device-lost') {
    return {
      status: 'device-lost',
      label: 'Preview Device Lost',
      message: lastError || 'The WebGPU device was lost. Remount the preview to recover the live renderer surface.',
      capability,
      webgpuStatus,
      fallbackActive: false,
      canRecover: true,
      lastError,
    }
  }

  if (webgpuStatus === 'recovering') {
    return {
      status: 'recovering',
      label: 'Preview Recovering',
      message: 'Renderer preview is recovering the WebGPU compositor after a remount or runtime interruption.',
      capability,
      webgpuStatus,
      fallbackActive: false,
      canRecover: true,
      lastError,
    }
  }

  if (webgpuStatus === 'error') {
    return {
      status: 'error',
      label: 'Preview Error',
      message: lastError || 'Renderer preview failed to initialize the WebGPU compositor for this workspace session.',
      capability,
      webgpuStatus,
      fallbackActive: false,
      canRecover: true,
      lastError,
    }
  }

  if (sceneWebGpuReady) {
    if (fallbackActive) {
      return {
        status: 'fallback-active',
        label: 'Fallback Scene Active',
        message:
          'Renderer preview is live through WebGPU, but the default engine fallback scene is still active until real template and asset context is available.',
        capability,
        webgpuStatus,
        fallbackActive: true,
        canRecover: false,
        lastError,
      }
    }

    return {
      status: 'running',
      label: 'Preview Running',
      message: 'Renderer preview is live through the WebGPU compositor.',
      capability,
      webgpuStatus,
      fallbackActive: false,
      canRecover: false,
      lastError,
    }
  }

  if (webgpuStatus === 'initializing' || webgpuStatus === 'idle') {
    return {
      status: 'initializing',
      label: 'Preview Initializing',
      message: 'Renderer preview is initializing the WebGPU compositor.',
      capability,
      webgpuStatus,
      fallbackActive: false,
      canRecover: false,
      lastError,
    }
  }

  if (fallbackActive) {
    return {
      status: 'fallback-active',
      label: 'Fallback Scene Active',
      message:
        'Renderer preview is live through WebGPU, but the default engine fallback scene is still active until real template and asset context is available.',
      capability,
      webgpuStatus,
      fallbackActive: true,
      canRecover: false,
      lastError,
    }
  }

  return {
    status: 'running',
    label: 'Preview Running',
    message: 'Renderer preview is live through the WebGPU compositor.',
    capability,
    webgpuStatus,
    fallbackActive: false,
    canRecover: false,
    lastError,
  }
}
