import type { PreviewFrameTelemetry } from '@/features/video/preview/previewFrameTelemetry'
import type { PreviewPerformanceSceneId } from '@/features/video/preview/previewPerformanceScenes'
import type { PreviewQualityTier } from '@/features/video/preview/previewQualityPolicy'
import type { SpectrumLayerPreview } from '@/features/video/domains/spectrum/spectrumLayerModel'
import type {
  WebGpuParticleInstance,
  WebGpuSpectrumInstance,
} from '@/features/video/webgpu/webgpuSpectrumRenderer'

type ApplyPreviewFrameReportOptions = {
  frameStart: number
  gpuTiming: {
    instancesMs: number
    particlesMs: number
    renderMs: number
  }
  dpr: number
  logicalWidth: number
  logicalHeight: number
  timestamp: number
  spectrumBarCount: number
  spectrumLayers: ReadonlyArray<SpectrumLayerPreview>
  qualityTier: PreviewQualityTier
  adaptiveQualityLevel: 0 | 1 | 2
  performanceScene: PreviewPerformanceSceneId
  gpuInstances: ReadonlyArray<WebGpuSpectrumInstance>
  gpuParticles: ReadonlyArray<WebGpuParticleInstance>
  useWebGpuSpectrum: boolean
  showDomPreviewBackground: boolean
  showDomPreviewLogo: boolean
  hasPostFx: boolean
  telemetry: PreviewFrameTelemetry
}

export function applyPreviewFrameReport({
  frameStart,
  gpuTiming,
  dpr,
  logicalWidth,
  logicalHeight,
  timestamp,
  spectrumBarCount,
  spectrumLayers,
  qualityTier,
  adaptiveQualityLevel,
  performanceScene,
  gpuInstances,
  gpuParticles,
  useWebGpuSpectrum,
  showDomPreviewBackground,
  showDomPreviewLogo,
  hasPostFx,
  telemetry,
}: ApplyPreviewFrameReportOptions): void {
  telemetry.recordTiming('instances', gpuTiming.instancesMs)
  telemetry.recordTiming('particles', gpuTiming.particlesMs)
  telemetry.recordTiming('render', gpuTiming.renderMs)

  const frameMs = performance.now() - frameStart
  telemetry.recordFrame(frameMs)
  telemetry.reportFrame(timestamp, {
    dpr: Number(dpr.toFixed(2)),
    width: Math.round(logicalWidth),
    height: Math.round(logicalHeight),
    barCount: spectrumBarCount,
    layerCount: spectrumLayers.length,
    qualityTier,
    adaptiveQualityLevel,
    performanceScene,
    instanceCount: gpuInstances.length,
    particleCount: gpuParticles.length,
    useWebGpuSpectrum,
    showDomPreviewBackground,
    showDomPreviewLogo,
    postFx: hasPostFx,
  })
}
