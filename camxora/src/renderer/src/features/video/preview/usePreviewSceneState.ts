import { useEffect, useMemo } from 'react'
import type { CSSProperties, MutableRefObject } from 'react'

import type {
  PreviewBackgroundPresentationDraft,
  PreviewLogoPresentationDraft,
  PreviewSpectrumBarCountDraft,
  PreviewTextDraft,
} from '@/features/video/core/contracts/previewDraftContracts'
import type { VideoTemplateDraft } from '@/features/video/core/contracts/videoTemplateDraft'
import {
  resolveSpectrumAttachment,
  type SpectrumAttachment,
} from '@/features/video/core/scene/attachmentService'
import { computePreviewSceneScale } from '@/features/video/core/contracts/renderSceneRequest'
import {
  buildSpectrumLayers,
  type SpectrumLayerPreview,
} from '@/features/video/domains/spectrum/spectrumLayerModel'
import {
  buildVideoPreviewScene,
  type VideoPreviewScene,
} from '@/features/video/preview/previewScene'
import {
  clampPreviewSpectrumBarCount,
  type PreviewGpuCapabilityProfile,
  type PreviewQualityPolicy,
} from '@/features/video/preview/previewQualityPolicy'
import type { PreviewBounds, PreviewSurfaceStatus } from '@/features/video/preview/usePreviewSurfaceLifecycle'
import type { PreviewAssetLoadStatus } from '@/features/video/preview/usePreviewAssetManager'
import type { RendererPreviewCapability } from '@/features/video/useRendererVideoPreview'
import { createVideoDebugSender } from '@/features/video/videoDiagnostics'
import type { VideoWorkspaceState } from '@/shared/types/desktop'

const sendPreviewReactivityDebug = createVideoDebugSender({
  sessionId: 'particle-motion-stuck',
  runId: 'pre-fix',
})

export type ResolveTextOverlayStateOptions = {
  currentPlaybackTimeSec: number
  scale: number
  selectedTextOverlayIndex: number
  templateDraft: PreviewTextDraft
}

export type ResolveTextOverlayStateResult<TOverlay> = {
  activeTextOverlays: ReadonlyArray<TOverlay>
  enabledTextOverlayCount: number
}

export type ResolveSpectrumBarCountOptions = {
  bounds: PreviewBounds
  scale: number
  spectrumAttachment: SpectrumAttachment | null
  spectrumLayers: SpectrumLayerPreview[]
  templateDraft: PreviewSpectrumBarCountDraft
}

export type BuildDomBackgroundStyleOptions = {
  backgroundImage: HTMLImageElement | null
  bounds: PreviewBounds
  currentPlaybackTimeSec: number
  templateDraft: PreviewBackgroundPresentationDraft
}

export type BuildDomLogoStyleOptions = {
  bounds: PreviewBounds
  currentPlaybackTimeSec: number
  scale: number
  templateDraft: PreviewLogoPresentationDraft
}

type UsePreviewSceneStateOptions<TOverlay> = {
  backgroundImageRef: MutableRefObject<HTMLImageElement | null>
  backgroundLoadStatus: PreviewAssetLoadStatus
  backgroundSrc: string | null
  bounds: PreviewBounds
  buildDomBackgroundStyle: (options: BuildDomBackgroundStyleOptions) => CSSProperties
  buildDomLogoStyle: (options: BuildDomLogoStyleOptions) => CSSProperties
  capability: RendererPreviewCapability
  capabilityProfile: PreviewGpuCapabilityProfile
  logoLoadStatus: PreviewAssetLoadStatus
  logoSrc: string | null
  logoVisibleRadiusRatio: number
  qualityPolicy: PreviewQualityPolicy
  resolveSpectrumBarCount: (options: ResolveSpectrumBarCountOptions) => number
  resolveTextOverlayState: (
    options: ResolveTextOverlayStateOptions,
  ) => ResolveTextOverlayStateResult<TOverlay>
  selectedMp3Path: string
  selectedTextOverlayIndex: number
  template: Record<string, unknown>
  templateDraft: VideoTemplateDraft
  webgpuStatus: PreviewSurfaceStatus
  workspace: Pick<VideoWorkspaceState, 'previewAspectRatio' | 'playback'>
}

export function usePreviewSceneState<TOverlay>({
  backgroundImageRef,
  backgroundLoadStatus,
  backgroundSrc,
  bounds,
  buildDomBackgroundStyle,
  buildDomLogoStyle,
  capability,
  capabilityProfile,
  logoLoadStatus,
  logoSrc,
  logoVisibleRadiusRatio,
  qualityPolicy,
  resolveSpectrumBarCount,
  resolveTextOverlayState,
  selectedMp3Path,
  selectedTextOverlayIndex,
  template,
  templateDraft,
  webgpuStatus,
  workspace,
}: UsePreviewSceneStateOptions<TOverlay>): VideoPreviewScene<TOverlay> {
  const scale = useMemo(
    () => computePreviewSceneScale(bounds, workspace.previewAspectRatio),
    [bounds, workspace.previewAspectRatio],
  )

  const currentPlaybackTimeSec = Number.isFinite(workspace.playback.currentTimeSec)
    ? workspace.playback.currentTimeSec
    : 0

  const { activeTextOverlays, enabledTextOverlayCount } = useMemo(
    () =>
      resolveTextOverlayState({
        currentPlaybackTimeSec,
        scale,
        selectedTextOverlayIndex,
        templateDraft,
      }),
    [currentPlaybackTimeSec, resolveTextOverlayState, scale, selectedTextOverlayIndex, templateDraft],
  )

  const spectrumLayerSource = useMemo(
    () =>
      ({
        ...template,
        style: templateDraft.style,
      }) as Record<string, unknown>,
    [template, templateDraft.style],
  )
  const spectrumLayers = useMemo(
    () => buildSpectrumLayers(spectrumLayerSource),
    [spectrumLayerSource],
  )
  const spectrumAttachment = useMemo(
    () => resolveSpectrumAttachment(templateDraft, spectrumLayers, scale, logoVisibleRadiusRatio, null),
    [logoVisibleRadiusRatio, scale, spectrumLayers, templateDraft],
  )
  const spectrumBarCount = useMemo(
    () =>
      clampPreviewSpectrumBarCount(
        resolveSpectrumBarCount({
        bounds,
        scale,
        spectrumAttachment,
        spectrumLayers,
        templateDraft,
        }),
        qualityPolicy,
      ),
    [bounds, qualityPolicy, resolveSpectrumBarCount, scale, spectrumAttachment, spectrumLayers, templateDraft],
  )

  const domBackgroundStyle = useMemo(
    () =>
      buildDomBackgroundStyle({
        backgroundImage: backgroundImageRef.current,
        bounds,
        currentPlaybackTimeSec,
        templateDraft,
      }),
    [backgroundImageRef, bounds, buildDomBackgroundStyle, currentPlaybackTimeSec, templateDraft],
  )

  const domLogoStyle = useMemo(
    () =>
      buildDomLogoStyle({
        bounds,
        currentPlaybackTimeSec,
        scale,
        templateDraft,
      }),
    [bounds, buildDomLogoStyle, currentPlaybackTimeSec, scale, templateDraft],
  )

  const scene = useMemo(
    () =>
      buildVideoPreviewScene({
        bounds,
        currentPlaybackTimeSec,
        draft: templateDraft,
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
        playback: { isReady: workspace.playback.isReady },
        spectrumAttachment,
        spectrumBarCount,
        spectrumLayers,
        activeTextOverlays,
        enabledTextOverlayCount,
        qualityPolicy,
        capability,
        webgpuStatus,
      }),
    [
      activeTextOverlays,
      backgroundLoadStatus,
      backgroundSrc,
      bounds,
      capability,
      capabilityProfile,
      currentPlaybackTimeSec,
      domBackgroundStyle,
      domLogoStyle,
      enabledTextOverlayCount,
      logoLoadStatus,
      logoSrc,
      logoVisibleRadiusRatio,
      qualityPolicy,
      scale,
      selectedMp3Path,
      spectrumAttachment,
      spectrumBarCount,
      spectrumLayers,
      templateDraft,
      webgpuStatus,
      workspace.playback.isReady,
    ],
  )

  useEffect(() => {
    // #region debug-point A:scene-assembly
    sendPreviewReactivityDebug({
      hypothesisId: 'A',
      location: 'usePreviewSceneState',
      msg: '[DEBUG] preview scene assembly snapshot',
      data: {
        selectedMp3Path,
        templateStyle: String(template.style ?? ''),
        templateDraftStyle: String(templateDraft.style ?? ''),
        sceneSpectrumStyle: String(scene.spectrumNode.style ?? ''),
        spectrumEnabled: Boolean(templateDraft.spectrumEnabled),
        backgroundBrightness: Number(templateDraft.backgroundBrightness ?? 0),
        logoOpacity: Number(templateDraft.logoOpacity ?? 0),
        particlesEnabled: Boolean(templateDraft.particlesEnabled),
        particlesVariant: String(templateDraft.particlesVariant ?? ''),
        particlesStyle: String(templateDraft.particlesStyle ?? ''),
        particlesSpawnMode: String(templateDraft.particlesSpawnMode ?? ''),
        particlesSpawnArea: String(templateDraft.particlesSpawnArea ?? ''),
        particlesMaxCount: Number(templateDraft.particlesMaxCount ?? 0),
        particlesSpeed: Number(templateDraft.particlesSpeed ?? 0),
        particlesOpacity: Number(templateDraft.particlesOpacity ?? 0),
        spectrumLayerCount: scene.spectrumNode.layers.length,
        spectrumBarCount: scene.spectrumNode.barCount,
        backgroundLoadStatus,
        logoLoadStatus,
        webgpuStatus,
        playbackReady: Boolean(workspace.playback.isReady),
      },
    })
    // #endregion
  }, [
    backgroundLoadStatus,
    logoLoadStatus,
    scene,
    selectedMp3Path,
    template,
    templateDraft,
    webgpuStatus,
    workspace.playback.isReady,
  ])

  return scene
}
