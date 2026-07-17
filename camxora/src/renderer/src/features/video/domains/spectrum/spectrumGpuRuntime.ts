import type {
  SpectrumGpuPreparationRequest,
  SpectrumGpuPreparationResult,
} from '@/features/video/domains/spectrum/spectrumGpuContract'
import { normalizeSpectrumStyleKey } from '@/features/video/domains/spectrum/spectrumLayerModel'
import {
  buildWebGpuSpectrumGradientAtlas,
  buildWebGpuSpectrumInstances,
} from '@/features/video/domains/spectrum/spectrumRendererAdapter'
import type { WebGpuSpectrumInstance } from '@/features/video/webgpu/webgpuSpectrumRenderer'
import {
  resolveSpectrumAttachment,
} from '@/features/video/core/scene/attachmentService'

export function buildSpectrumGpuInstances({
  analysedFrame,
  audioSignal,
  buildLayerSpectrumValues,
  buildSyntheticSpectrumValues,
  centerX,
  centerY,
  hasBoundAudio,
  motionState,
  reactiveEnergy,
  scale,
  spectrumAttachment: _initialAttachment,
  spectrumBarCount,
  spectrumLayers,
  templateDraft,
  timeSec,
  useWebGpuSpectrum,
  logoPresentationState = null,
}: SpectrumGpuPreparationRequest): SpectrumGpuPreparationResult {
  if (!templateDraft.spectrumEnabled || !spectrumLayers.length || !useWebGpuSpectrum) {
    return {
      gradientAtlas: null,
      gpuInstances: [],
      instancesMs: 0,
    }
  }

  // Compute spectrum attachment using the dynamic logo presentation state every frame!
  const spectrumAttachment = resolveSpectrumAttachment(
    templateDraft,
    spectrumLayers,
    scale,
    logoPresentationState ? 1 : 0, // visible radius ratio doesn't matter if we have dynamic state
    logoPresentationState,
  )

  const gpuInstances: WebGpuSpectrumInstance[] = []
  const gradientAtlas = buildWebGpuSpectrumGradientAtlas(spectrumLayers)
  const attachedLayerBaseOffset = spectrumAttachment.attachedToLogo
    ? spectrumLayers.reduce(
        (minValue, layer) => Math.min(minValue, Math.max(0, layer.radiusOffset)),
        Number.POSITIVE_INFINITY,
      )
    : 0

  // If attached to logo, use the dynamic logo center!
  const renderCenterX = spectrumAttachment.attachedToLogo ? spectrumAttachment.centerOffsetX : centerX
  const renderCenterY = spectrumAttachment.attachedToLogo ? spectrumAttachment.centerOffsetY : centerY

  const instancesStart = performance.now()
  spectrumLayers.forEach((layer, layerIndex) => {
    const signalValues = layer.mirrored ? audioSignal?.mirroredRenderValues : audioSignal?.renderValues
    const layerValues =
      (signalValues?.length ? signalValues : null) ??
      buildLayerSpectrumValues(spectrumBarCount, analysedFrame, layer.mirrored) ??
      (hasBoundAudio
        ? Array.from({ length: spectrumBarCount }, () => 0)
        : buildSyntheticSpectrumValues(
            spectrumBarCount,
            timeSec,
            templateDraft.audioInputGain,
            templateDraft.audioMotionSmoothing,
            layerIndex,
          ))
    const radiusBase =
      spectrumAttachment.baseRadius +
      (spectrumAttachment.attachedToLogo
        ? Math.max(
            0,
            Math.max(0, layer.radiusOffset) -
              (Number.isFinite(attachedLayerBaseOffset) ? attachedLayerBaseOffset : 0),
          ) *
            scale *
            0.35
        : layer.radiusOffset * scale * 0.35) +
      layerIndex * 8 * scale

    gpuInstances.push(
      ...buildWebGpuSpectrumInstances(
        renderCenterX,
        renderCenterY,
        radiusBase,
        layer,
        layerValues,
        reactiveEnergy,
        scale,
        normalizeSpectrumStyleKey(layer.styleKey) === 'flying-glow'
          ? motionState.flyingGlowPulseDrive
          : analysedFrame?.styleMotionDrive,
        {
          gradientV: (layerIndex + 0.5) / Math.max(1, gradientAtlas.height),
          heightScale: templateDraft.audioBarHeight,
        },
      ),
    )
  })

  return {
    gradientAtlas,
    gpuInstances,
    instancesMs: performance.now() - instancesStart,
  }
}
