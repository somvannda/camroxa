import { useCallback, useRef } from 'react'

import {
  createParticleSimulationState,
  type ParticleSimulationState,
} from '@/features/video/domains/particles/particleSimulation'
import type {
  PreviewProviderOptions,
  PreviewProviderRenderState,
} from '@/features/video/preview/previewProviderContract'
import { runPreviewFrame } from '@/features/video/preview/previewFrameRunner'
import { createPreviewRuntimeDiagnostics } from '@/features/video/preview/previewRuntimeDiagnostics'
import type { PreviewReactiveMotionState } from '@/features/video/preview/previewReactiveFrameState'
import { usePreviewAssetService } from '@/features/video/preview/usePreviewAssetService'
import { usePreviewRuntime } from '@/features/video/preview/usePreviewRuntime'
import {
  buildPreviewLifecycleState,
  type PreviewLifecycleState,
} from '@/features/video/preview/previewLifecycleState'
import {
  usePreviewSceneState,
} from '@/features/video/preview/usePreviewSceneState'
import { usePreviewSurfaceLifecycle } from '@/features/video/preview/usePreviewSurfaceLifecycle'
import { usePreviewTransportCoordinator } from '@/features/video/preview/usePreviewTransportCoordinator'

export function usePreviewProviderState<TOverlay>({
  backgroundPath,
  buildDomBackgroundStyle,
  buildDomLogoStyle,
  buildLayerSpectrumValues,
  buildSyntheticSpectrumValues,
  drawBackgroundLayer,
  drawLogoLayer,
  drawTextOverlays,
  logoPath,
  onPlaybackStateChange,
  playbackCommand,
  previewVolume,
  runtimeMode = 'live',
  resolveAnchorPoint,
  resolveSpectrumBarCount,
  resolveTextOverlayState,
  selectedMp3Path,
  selectedTextOverlayIndex,
  smoothPreviewReactiveValue,
  template,
  templateDraft,
  updateFlyingGlowWingEnvelope,
  averageValues,
  applyDomBackgroundPresentation,
  applyDomLogoPresentation,
  workspace,
}: PreviewProviderOptions<TOverlay>): PreviewProviderRenderState<TOverlay> {
  const domBackgroundImageRef = useRef<HTMLImageElement | null>(null)
  const domLogoLayerRef = useRef<HTMLDivElement | null>(null)
  const previewMotionRef = useRef<PreviewReactiveMotionState>({
    backgroundEnergy: 0,
    backgroundBeatBaseline: 0,
    backgroundPulseDrive: 0,
    logoEnergy: 0,
    logoBeatBaseline: 0,
    logoPulseDrive: 0,
    flyingGlowLastTriggerDrive: 0,
    flyingGlowPulseDrive: 0,
    flyingGlowLastTriggerSec: -1,
    flyingGlowBeatIntervalSec: 0.2,
  })
  const particleStateRef = useRef<ParticleSimulationState>(createParticleSimulationState())

  const {
    backgroundImageRef,
    backgroundLoadStatus,
    backgroundSrc,
    capability,
    logoImageRef,
    logoLoadStatus,
    logoSrc,
    logoVisibleRadiusRatio,
  } = usePreviewAssetService({
    backgroundPath,
    logoEnabled: templateDraft.logoEnabled,
    logoPath,
    logoShape: templateDraft.logoShape,
  })

  const {
    backdropCanvasRef,
    bounds,
    capabilityProfile,
    containerRef,
    onTelemetryReport,
    overlayCanvasRef,
    performanceVerification,
    qualityPolicy,
    webgpuCanvasRef,
    webgpuErrorMessage,
    webgpuRendererRef,
    webgpuStatus,
  } = usePreviewSurfaceLifecycle({
    capability,
  })

  const {
    audioRuntimeRef,
    lastPlaybackReportAtRef,
    reportPlaybackState,
  } = usePreviewTransportCoordinator({
    audioMotionSmoothing: templateDraft.audioMotionSmoothing ?? 0.8,
    onPlaybackStateChange,
    playbackCommand,
    previewVolume,
    selectedMp3Path,
  })

  const manualRuntimeDiagnosticsRef = useRef<ReturnType<typeof createPreviewRuntimeDiagnostics> | null>(null)
  if (!manualRuntimeDiagnosticsRef.current) {
    manualRuntimeDiagnosticsRef.current = createPreviewRuntimeDiagnostics({
      onReport: onTelemetryReport,
    })
  }

  const scene = usePreviewSceneState({
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
  })
  const sceneRef = useRef(scene)
  sceneRef.current = scene

  usePreviewRuntime({
    audioRuntimeRef,
    backdropCanvasRef,
    backgroundImageRef,
    buildLayerSpectrumValues,
    buildSyntheticSpectrumValues,
    domBackgroundImageRef,
    domLogoLayerRef,
    drawBackgroundLayer,
    drawLogoLayer,
    drawTextOverlays,
    logoImageRef,
    overlayCanvasRef,
    particleStateRef,
    previewMotionRef,
    reportPlaybackState,
    resolveAnchorPoint,
    runtimeMode,
    scene,
    smoothPreviewReactiveValue,
    updateFlyingGlowWingEnvelope,
    webgpuCanvasRef,
    webgpuRendererRef,
    averageValues,
    applyDomBackgroundPresentation,
    applyDomLogoPresentation,
    onTelemetryReport,
    lastPlaybackReportAtRef,
  })

  const manualRenderFrame = useCallback(
    ({
      previousTimestampMs,
      timestampMs,
      playbackTimeSec,
    }: {
      previousTimestampMs: number
      timestampMs: number
      playbackTimeSec?: number
    }) => {
      runPreviewFrame<TOverlay>({
        frame: {
          previousTimestamp: previousTimestampMs,
          timestamp: timestampMs,
        },
        telemetry: manualRuntimeDiagnosticsRef.current?.telemetry ?? createPreviewRuntimeDiagnostics().telemetry,
        audioRuntimeRef,
        backdropCanvasRef,
        backgroundImageRef,
        buildLayerSpectrumValues,
        buildSyntheticSpectrumValues,
        domBackgroundImageRef,
        domLogoLayerRef,
        drawBackgroundLayer,
        drawLogoLayer,
        drawTextOverlays,
        logoImageRef,
        overlayCanvasRef,
        particleStateRef,
        previewMotionRef,
        reportPlaybackState,
        resolveAnchorPoint,
        scene: sceneRef.current,
        smoothPreviewReactiveValue,
        updateFlyingGlowWingEnvelope,
        webgpuRendererRef,
        averageValues,
        applyDomBackgroundPresentation,
        applyDomLogoPresentation,
        lastPlaybackReportAtRef,
        forcePlaybackActive: runtimeMode === 'manual-export',
        playbackTimeSecOverride: playbackTimeSec,
      })
    },
    [
      audioRuntimeRef,
      backdropCanvasRef,
      backgroundImageRef,
      buildLayerSpectrumValues,
      buildSyntheticSpectrumValues,
      domBackgroundImageRef,
      domLogoLayerRef,
      drawBackgroundLayer,
      drawLogoLayer,
      drawTextOverlays,
      logoImageRef,
      overlayCanvasRef,
      particleStateRef,
      previewMotionRef,
      reportPlaybackState,
      resolveAnchorPoint,
      smoothPreviewReactiveValue,
      updateFlyingGlowWingEnvelope,
      webgpuRendererRef,
      averageValues,
      applyDomBackgroundPresentation,
      applyDomLogoPresentation,
      lastPlaybackReportAtRef,
      runtimeMode,
    ],
  )

  const lifecycleState: PreviewLifecycleState = buildPreviewLifecycleState({
    capability,
    lastError: webgpuErrorMessage,
    scene,
    webgpuStatus,
  })

  return {
    containerRef,
    domBackgroundImageRef,
    domLogoLayerRef,
    lifecycleState,
    manualRenderFrame: runtimeMode === 'manual-export' ? manualRenderFrame : null,
    playbackReady: workspace.playback.isReady,
    performanceVerification,
    scene,
    webgpuCanvasRef,
    webgpuRendererRef,
  }
}
