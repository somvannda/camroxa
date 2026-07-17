import type { CSSProperties } from 'react'

import type {
  PreviewDomPresentationDraft,
  PreviewFramePositionDraft,
  PreviewGpuRuntimeDraft,
  PreviewReactiveFrameDraft,
  PreviewSceneDraft,
} from '@/features/video/core/contracts/previewDraftContracts'
import {
  pickPreviewDomPresentationDraft,
  pickPreviewFramePositionDraft,
  pickPreviewGpuRuntimeDraft,
  pickPreviewReactiveFrameDraft,
} from '@/features/video/core/contracts/previewDraftContracts'
import type { SpectrumAttachment } from '@/features/video/core/scene/attachmentService'
import type { SpectrumLayerPreview } from '@/features/video/domains/spectrum/spectrumLayerModel'
import {
  resolvePreviewPerformanceNode,
  type PreviewPerformanceNode,
} from '@/features/video/preview/previewPerformanceScenes'
import type {
  PreviewGpuCapabilityProfile,
  PreviewQualityPolicy,
} from '@/features/video/preview/previewQualityPolicy'
import type { PreviewAssetLoadStatus } from '@/features/video/preview/usePreviewAssetManager'
import type { RendererPreviewCapability } from '@/features/video/useRendererVideoPreview'
import type { VideoWorkspaceState } from '@/shared/types/desktop'

type PreviewBounds = {
  width: number
  height: number
}

export type VideoPreviewGpuNode = {
  atmosphereEnabled: boolean
  submitFallbackScene: boolean
  submitSpectrumInstances: boolean
}

export type VideoPreviewRuntimeNode = {
  positionDraft: PreviewFramePositionDraft
  reactiveDraft: PreviewReactiveFrameDraft
  gpuDrafts: PreviewGpuRuntimeDraft
  presentationDraft: PreviewDomPresentationDraft
}

export type VideoPreviewScene<TTextOverlay> = {
  viewport: {
    bounds: PreviewBounds
    scale: number
    backgroundSrc: string | null
    logoSrc: string | null
    showFallbackScene: boolean
    showDomPreviewBackground: boolean
    showDomPreviewLogo: boolean
    webgpuReady: boolean
  }
  gpuNode: VideoPreviewGpuNode
  runtimeNode: VideoPreviewRuntimeNode
  transport: {
    currentPlaybackTimeSec: number
    selectedMp3Path: string
    playback: Pick<VideoWorkspaceState['playback'], 'isReady'>
  }
  capability: {
    label: string
    message: string
  }
  quality: {
    capabilityProfile: PreviewGpuCapabilityProfile
    policy: PreviewQualityPolicy
  }
  performance: PreviewPerformanceNode
  backgroundNode: {
    enabled: boolean
    src: string | null
    loadStatus: PreviewAssetLoadStatus
    domStyle: CSSProperties
  }
  logoNode: {
    enabled: boolean
    src: string | null
    loadStatus: PreviewAssetLoadStatus
    visibleRadiusRatio: number
    domStyle: CSSProperties
  }
  spectrumNode: {
    enabled: boolean
    style: string
    layers: SpectrumLayerPreview[]
    attachment: SpectrumAttachment | null
    barCount: number
    flyingGlowWingRelease: number
  }
  particlesNode: {
    enabled: boolean
  }
  textNodes: {
    active: ReadonlyArray<TTextOverlay>
    enabledCount: number
  }
  statusBadges: string[]
}

type BuildVideoPreviewSceneOptions<TTextOverlay> = {
  bounds: PreviewBounds
  currentPlaybackTimeSec: number
  draft: PreviewSceneDraft
  backgroundSrc: string | null
  backgroundLoadStatus: PreviewAssetLoadStatus
  capabilityProfile: PreviewGpuCapabilityProfile
  domBackgroundStyle: CSSProperties
  domLogoStyle: CSSProperties
  logoLoadStatus: PreviewAssetLoadStatus
  logoSrc: string | null
  logoVisibleRadiusRatio: number
  scale: number
  selectedMp3Path: string
  playback: Pick<VideoWorkspaceState['playback'], 'isReady'>
  spectrumAttachment: SpectrumAttachment | null
  spectrumBarCount: number
  spectrumLayers: SpectrumLayerPreview[]
  activeTextOverlays: ReadonlyArray<TTextOverlay>
  enabledTextOverlayCount: number
  qualityPolicy: PreviewQualityPolicy
  capability: RendererPreviewCapability
  webgpuStatus: 'idle' | 'unsupported' | 'initializing' | 'ready' | 'recovering' | 'device-lost' | 'error'
}

export function buildVideoPreviewScene<TTextOverlay>({
  bounds,
  currentPlaybackTimeSec,
  draft,
  backgroundSrc,
  backgroundLoadStatus,
  capabilityProfile,
  domBackgroundStyle,
  domLogoStyle,
  logoLoadStatus,
  logoSrc,
  logoVisibleRadiusRatio,
  scale,
  selectedMp3Path,
  playback,
  spectrumAttachment,
  spectrumBarCount,
  spectrumLayers,
  activeTextOverlays,
  enabledTextOverlayCount,
  qualityPolicy,
  capability,
  webgpuStatus,
}: BuildVideoPreviewSceneOptions<TTextOverlay>): VideoPreviewScene<TTextOverlay> {
  const webgpuReady = webgpuStatus === 'ready'
  const useWebGpuSpectrum = webgpuReady && spectrumLayers.length > 0
  const backgroundEnabled = draft.backgroundEnabled
  const resolvedBackgroundSrc = backgroundEnabled ? backgroundSrc : null
  const resolvedBackgroundLoadStatus = backgroundEnabled ? backgroundLoadStatus : 'idle'
  const showFallbackScene = backgroundEnabled && !resolvedBackgroundSrc
  const atmosphereEnabled = draft.smokeEnabled || draft.vignetteEnabled
  const showDomPreviewBackground =
    backgroundEnabled && resolvedBackgroundLoadStatus === 'ready' && Boolean(resolvedBackgroundSrc)
  const showDomPreviewLogo = draft.logoEnabled && logoLoadStatus === 'ready' && Boolean(logoSrc)
  const submitFallbackScene = showFallbackScene && !showDomPreviewBackground
  const runtimeNode: VideoPreviewRuntimeNode = {
    positionDraft: pickPreviewFramePositionDraft(draft),
    reactiveDraft: pickPreviewReactiveFrameDraft(draft),
    gpuDrafts: pickPreviewGpuRuntimeDraft(draft),
    presentationDraft: pickPreviewDomPresentationDraft(draft),
  }
  const performanceNode = resolvePreviewPerformanceNode({
    draft,
    enabledTextOverlayCount,
    qualityPolicy,
    spectrumBarCount,
    spectrumLayers,
  })

  let capabilityLabel = 'WebGPU Required'
  let capabilityMessage =
    'Renderer preview requires the WebGPU compositor for spectrum rendering. The old Canvas path is no longer used for live spectrum preview.'

  if (webgpuReady) {
    capabilityLabel = 'WebGPU Compositor Live'
    capabilityMessage = showFallbackScene
      ? 'Renderer preview is live through one WebGPU compositor surface. A default engine fallback scene is active until you load a real template.'
      : 'Renderer preview is live through one WebGPU compositor surface. Background, smoke, vignette, logo, timed text, spectrum, and particles now feed the GPU preview canvas.'
  } else if (webgpuStatus === 'recovering') {
    capabilityLabel = 'WebGPU Recovering'
    capabilityMessage = 'Renderer preview is recovering the WebGPU compositor after a remount or runtime interruption.'
  } else if (webgpuStatus === 'device-lost') {
    capabilityLabel = 'WebGPU Device Lost'
    capabilityMessage = 'The WebGPU device was lost. Remount the preview surface to recover the compositor.'
  } else if (webgpuStatus === 'initializing' || webgpuStatus === 'idle') {
    capabilityLabel = 'WebGPU Starting'
    capabilityMessage = 'Renderer preview is initializing the WebGPU compositor.'
  } else if (capability !== 'webgpu') {
    capabilityLabel = 'WebGPU Required'
    capabilityMessage = 'This machine does not currently expose WebGPU to the Electron renderer, so the GPU spectrum preview cannot start.'
  } else if (webgpuStatus === 'error') {
    capabilityLabel = 'WebGPU Error'
    capabilityMessage = 'Renderer preview failed to initialize the WebGPU compositor.'
  }

  const statusBadges: string[] = []
  if (webgpuReady) {
    statusBadges.push('Compositor surface active')
  }
  if (draft.particlesEnabled) {
    statusBadges.push('GPU particles active')
  }

  return {
    viewport: {
      bounds,
      scale,
      backgroundSrc: resolvedBackgroundSrc,
      logoSrc,
      showFallbackScene,
      showDomPreviewBackground,
      showDomPreviewLogo,
      webgpuReady,
    },
    gpuNode: {
      atmosphereEnabled,
      submitFallbackScene,
      submitSpectrumInstances: useWebGpuSpectrum,
    },
    runtimeNode,
    transport: {
      currentPlaybackTimeSec,
      selectedMp3Path,
      playback,
    },
    capability: {
      label: capabilityLabel,
      message: capabilityMessage,
    },
    quality: {
      capabilityProfile,
      policy: qualityPolicy,
    },
    performance: performanceNode,
    backgroundNode: {
      enabled: backgroundEnabled,
      src: resolvedBackgroundSrc,
      loadStatus: resolvedBackgroundLoadStatus,
      domStyle: domBackgroundStyle,
    },
    logoNode: {
      enabled: draft.logoEnabled,
      src: logoSrc,
      loadStatus: logoLoadStatus,
      visibleRadiusRatio: logoVisibleRadiusRatio,
      domStyle: domLogoStyle,
    },
    spectrumNode: {
      enabled: draft.spectrumEnabled,
      style: draft.style,
      layers: spectrumLayers,
      attachment: spectrumAttachment,
      barCount: spectrumBarCount,
      flyingGlowWingRelease: draft.flyingGlowWingRelease,
    },
    particlesNode: {
      enabled: draft.particlesEnabled,
    },
    textNodes: {
      active: activeTextOverlays,
      enabledCount: enabledTextOverlayCount,
    },
    statusBadges,
  }
}
