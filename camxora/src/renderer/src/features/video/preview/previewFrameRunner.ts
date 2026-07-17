import { renderPreviewDomFrame } from '@/features/video/preview/previewDomFrameRenderer'
import type { PreviewAnimationLoopFrame } from '@/features/video/preview/previewAnimationLoop'
import type { PreviewFrameExecutionOptions } from '@/features/video/preview/previewFrameContract'
import { applyPreviewFrameReport } from '@/features/video/preview/previewFrameReporter'
import { resolvePreviewFrameState } from '@/features/video/preview/previewFrameState'
import type { PreviewFrameTelemetry } from '@/features/video/preview/previewFrameTelemetry'
import { runPreviewGpuRuntimeCoordinator } from '@/features/video/preview/previewGpuRuntimeCoordinator'
import { applyPreviewPlaybackReport } from '@/features/video/preview/previewPlaybackReporter'
import { resolvePreviewReactiveFrameState } from '@/features/video/preview/previewReactiveFrameState'
import { normalizeSpectrumStyleKey } from '@/features/video/domains/spectrum/spectrumLayerModel'
import { createVideoDebugSender } from '@/features/video/videoDiagnostics'

const sendPreviewReactivityDebug = createVideoDebugSender({
  sessionId: 'particle-motion-stuck',
  runId: 'pre-fix',
})

const sendParticleReactColorDebug = createVideoDebugSender({
  sessionId: 'particle-react-color',
  runId: 'pre-fix',
})

type RunPreviewFrameOptions<TOverlay> = PreviewFrameExecutionOptions<TOverlay> & {
  frame: PreviewAnimationLoopFrame
  forcePlaybackActive?: boolean
  playbackTimeSecOverride?: number
  telemetry: PreviewFrameTelemetry
}

export function runPreviewFrame<TOverlay>({
  frame,
  forcePlaybackActive = false,
  playbackTimeSecOverride,
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
}: RunPreviewFrameOptions<TOverlay>): void {
  const { timestamp, previousTimestamp } = frame
  const normalizedSpectrumStyle = normalizeSpectrumStyleKey(scene.spectrumNode.style ?? '')
  const bounds = scene.viewport.bounds
  const scale = scene.viewport.scale
  const showDomPreviewBackground = scene.viewport.showDomPreviewBackground
  const showDomPreviewLogo = scene.viewport.showDomPreviewLogo
  const gpuNode = scene.gpuNode
  const activeTextOverlays = scene.textNodes.active
  const spectrumAttachment = scene.spectrumNode.attachment
  const spectrumBarCount = scene.spectrumNode.barCount
  const spectrumLayers = scene.spectrumNode.layers
  const qualityPolicy = scene.quality.policy
  const performanceScene = scene.performance.primaryScene
  const selectedMp3Path = scene.transport.selectedMp3Path
  const { positionDraft, reactiveDraft, gpuDrafts, presentationDraft } = scene.runtimeNode

  const runtime = audioRuntimeRef.current
  const frameStart = performance.now()

  const layoutStart = performance.now()
  const {
    logicalWidth,
    logicalHeight,
    dpr,
    centerX,
    centerY,
    deltaSec,
    timeSec,
  } = resolvePreviewFrameState({
    bounds,
    preferSharpSpectrumEdges: normalizedSpectrumStyle === 'flying-glow',
    scale,
    spectrumAttachment,
    positionDraft,
    qualityPolicy,
    timestamp,
    previousTimestamp,
    resolveAnchorPoint,
  })
  telemetry.recordTiming('layout', performance.now() - layoutStart)

  const playbackReport = applyPreviewPlaybackReport({
    runtime,
    timestamp,
    lastReportedAt: lastPlaybackReportAtRef.current,
    reportPlaybackState,
  })
  lastPlaybackReportAtRef.current = playbackReport.nextReportedAt

  const motionState = previewMotionRef.current
  const {
    analysedFrame,
    audioSignal,
    hasBoundAudio,
    reactiveEnergy,
    timing,
  } = resolvePreviewReactiveFrameState({
    averageValues,
    buildLayerSpectrumValues,
    buildSyntheticSpectrumValues,
    deltaSec,
    forcePlaybackActive,
    motionState,
      playbackTimeSecOverride,
    runtime,
    selectedMp3Path,
    smoothPreviewReactiveValue,
    spectrumBarCount,
    reactiveDraft,
    timeSec,
    updateFlyingGlowWingEnvelope,
  })
  telemetry.recordTiming('audio', timing.audioMs)
  telemetry.recordTiming('spectrum', timing.spectrumMs)

  const webgpuRenderer = webgpuRendererRef.current

  const canvas2dStart = performance.now()
  const { backdropSource, overlaySource, logoPresentationState } = renderPreviewDomFrame({
    activeTextOverlays,
    applyDomBackgroundPresentation,
    applyDomLogoPresentation,
    backdropCanvasRef,
    backgroundImageRef,
    bounds,
    domBackgroundImageRef,
    domLogoLayerRef,
    dpr,
    drawBackgroundLayer,
    drawLogoLayer,
    drawTextOverlays,
    logicalHeight,
    logicalWidth,
    logoImageRef,
    motionState,
    overlayCanvasRef,
    scale,
    showDomPreviewBackground,
    showDomPreviewLogo,
    presentationDraft,
    timeSec,
  })
  telemetry.recordTiming('canvas2d', performance.now() - canvas2dStart)

  const {
    gpuInstances,
    gpuParticles,
    hasPostFx,
    timing: gpuTiming,
  } = runPreviewGpuRuntimeCoordinator({
    analysedFrame,
    audioSignal,
    backdropSource,
    buildLayerSpectrumValues,
    buildSyntheticSpectrumValues,
    centerX,
    centerY,
    deltaSec,
    dpr,
    gpuNode,
    hasBoundAudio,
    logicalHeight,
    logicalWidth,
    motionState,
    overlaySource,
    particleState: particleStateRef.current,
    qualityPolicy,
    reactiveEnergy,
    runtime,
    scale,
    spectrumAttachment,
    spectrumBarCount,
    spectrumLayers,
    drafts: gpuDrafts,
    timeSec,
    webgpuRenderer,
    logoPresentationState,
  })

  if (Math.floor(timestamp / 1000) !== Math.floor(previousTimestamp / 1000)) {
    // #region debug-point B:frame-reactivity
    sendPreviewReactivityDebug({
      hypothesisId: 'B',
      location: 'previewFrameRunner',
      msg: '[DEBUG] preview reactive frame snapshot',
      data: {
        selectedMp3Path,
        currentPlaybackTimeSec: Number(scene.transport.currentPlaybackTimeSec.toFixed(3)),
        hasBoundAudio,
        playbackReady: Boolean(scene.transport.playback.isReady),
        reactiveEnergy: Number(reactiveEnergy.toFixed(4)),
        backgroundEnergy: Number(previewMotionRef.current.backgroundEnergy.toFixed(4)),
        backgroundPulseDrive: Number(previewMotionRef.current.backgroundPulseDrive.toFixed(4)),
        logoEnergy: Number(previewMotionRef.current.logoEnergy.toFixed(4)),
        logoPulseDrive: Number(previewMotionRef.current.logoPulseDrive.toFixed(4)),
        particlesEnabled: scene.particlesNode.enabled,
        particleCount: gpuParticles.length,
        particleMaxCount: Math.round(Number(gpuDrafts.particles.particlesMaxCount ?? 0)),
        particleSpawnRate: Math.round(Number(gpuDrafts.particles.particlesSpawnRate ?? 0)),
        particleSpawnMode: String(gpuDrafts.particles.particlesSpawnMode ?? ''),
        particleVariant: String(gpuDrafts.particles.particlesVariant ?? ''),
        particleStyle: String(gpuDrafts.particles.particlesStyle ?? ''),
        particleSpawnArea: String(gpuDrafts.particles.particlesSpawnArea ?? ''),
        particleSpawnThreshold: Number(Number(gpuDrafts.particles.particlesSpawnThreshold ?? 0).toFixed(3)),
        particleOpacity: Number(Number(gpuDrafts.particles.particlesOpacity ?? 0).toFixed(3)),
        particleSize: Number(Number(gpuDrafts.particles.particlesSize ?? 0).toFixed(2)),
        particleSpeed: Number(Number(gpuDrafts.particles.particlesSpeed ?? 0).toFixed(3)),
        particleDrift: Number(Number(gpuDrafts.particles.particlesDrift ?? 0).toFixed(3)),
        particleSwirl: Number(Number(gpuDrafts.particles.particlesSwirl ?? 0).toFixed(3)),
        particleColor: String(gpuDrafts.particles.particlesColor ?? ''),
        particleReactColor: String(gpuDrafts.particles.particlesReactColor ?? ''),
        particleReactStrength: Number(Number(gpuDrafts.particles.particlesReactStrength ?? 0).toFixed(3)),
        particleStateReactiveEnv: Number((particleStateRef.current.reactiveEnv ?? 0).toFixed(4)),
        particleStateTriggerEnv: Number((particleStateRef.current.triggerEnv ?? 0).toFixed(4)),
        particleStateTimeSec: Number((particleStateRef.current.timeSec ?? 0).toFixed(3)),
        spectrumEnabled: scene.spectrumNode.enabled,
        spectrumLayerCount: scene.spectrumNode.layers.length,
        gpuInstanceCount: gpuInstances.length,
      },
    })
    sendParticleReactColorDebug({
      hypothesisId: 'B',
      location: 'previewFrameRunner',
      msg: '[DEBUG] particle react-color preview draft snapshot',
      data: {
        selectedMp3Path,
        particlesEnabled: scene.particlesNode.enabled,
        particleCount: gpuParticles.length,
        particlesColor: String(gpuDrafts.particles.particlesColor ?? ''),
        particlesReactColor: String(gpuDrafts.particles.particlesReactColor ?? ''),
        particlesReactStrength: Number(Number(gpuDrafts.particles.particlesReactStrength ?? 0).toFixed(3)),
        particleStateReactiveEnv: Number((particleStateRef.current.reactiveEnv ?? 0).toFixed(4)),
        particleStateTriggerEnv: Number((particleStateRef.current.triggerEnv ?? 0).toFixed(4)),
        reactiveEnergy: Number(reactiveEnergy.toFixed(4)),
      },
    })
    // #endregion
  }

  applyPreviewFrameReport({
    frameStart,
    gpuTiming,
    dpr,
    logicalWidth,
    logicalHeight,
    timestamp,
    spectrumBarCount,
    spectrumLayers,
    qualityTier: qualityPolicy.tier,
    adaptiveQualityLevel: qualityPolicy.adaptiveQualityLevel,
    performanceScene,
    gpuInstances,
    gpuParticles,
    useWebGpuSpectrum: gpuNode.submitSpectrumInstances,
    showDomPreviewBackground,
    showDomPreviewLogo,
    hasPostFx,
    telemetry,
  })
}
