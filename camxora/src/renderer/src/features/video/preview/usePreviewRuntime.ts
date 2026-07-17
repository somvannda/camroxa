import { useEffect } from 'react'

import { startPreviewAnimationLoop } from '@/features/video/preview/previewAnimationLoop'
import type { PreviewRuntimeOptions } from '@/features/video/preview/previewFrameContract'
import { runPreviewFrame } from '@/features/video/preview/previewFrameRunner'
import { createPreviewRuntimeDiagnostics } from '@/features/video/preview/previewRuntimeDiagnostics'

export function usePreviewRuntime<TOverlay>({
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
  runtimeMode = 'live',
  resolveAnchorPoint,
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
}: PreviewRuntimeOptions<TOverlay>): void {
  useEffect(() => {
    if (runtimeMode !== 'live') {
      return
    }
    if (typeof navigator !== 'undefined' && /jsdom/i.test(navigator.userAgent)) {
      return
    }

    const canvas = webgpuCanvasRef.current
    if (!canvas) {
      return
    }

    const { telemetry } = createPreviewRuntimeDiagnostics({
      onReport: onTelemetryReport,
    })

    return startPreviewAnimationLoop({
      initialTimestamp: performance.now(),
      onFrame: ({ previousTimestamp, timestamp }) => {
        runPreviewFrame<TOverlay>({
          frame: {
            previousTimestamp,
            timestamp,
          },
          scene,
          audioRuntimeRef,
          lastPlaybackReportAtRef,
          previewMotionRef,
          particleStateRef,
          telemetry,
          reportPlaybackState,
          resolveAnchorPoint,
          averageValues,
          buildLayerSpectrumValues,
          buildSyntheticSpectrumValues,
          smoothPreviewReactiveValue,
          updateFlyingGlowWingEnvelope,
          backdropCanvasRef,
          backgroundImageRef,
          domBackgroundImageRef,
          domLogoLayerRef,
          drawBackgroundLayer,
          drawLogoLayer,
          drawTextOverlays,
          logoImageRef,
          overlayCanvasRef,
          applyDomBackgroundPresentation,
          applyDomLogoPresentation,
          webgpuRendererRef,
        })
      },
    })
  }, [
    runtimeMode,
    applyDomBackgroundPresentation,
    applyDomLogoPresentation,
    onTelemetryReport,
    averageValues,
    buildLayerSpectrumValues,
    buildSyntheticSpectrumValues,
    drawBackgroundLayer,
    drawLogoLayer,
    drawTextOverlays,
    reportPlaybackState,
    resolveAnchorPoint,
    scene,
    smoothPreviewReactiveValue,
    updateFlyingGlowWingEnvelope,
  ])
}
