import type { PreviewGpuAudioSignalFrame } from '@/features/video/core/contracts/previewGpuAudioSignalContract'
import {
  AUDIO_SPECTRUM_BINS,
  type AudioSpectrumFeatures,
  type AudioSpectrumFrame,
} from '@/features/video/preview/audioSpectrumAnalysis'

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value))
}

function mirrorValues(values: ArrayLike<number>): number[] {
  const mirrored = new Array<number>(values.length)
  const half = Math.floor(values.length / 2)

  for (let index = 0; index < half; index += 1) {
    mirrored[index] = values[half - 1 - index] ?? 0
  }
  for (let index = half; index < values.length; index += 1) {
    mirrored[index] = values[index - half] ?? 0
  }

  return mirrored
}

function resampleValues(values: ArrayLike<number>, count: number): number[] {
  if (count <= 0 || values.length <= 0) {
    return []
  }
  if (count === values.length) {
    return Array.from(values, (value) => clamp(Number(value) || 0, 0, 1))
  }

  return Array.from({ length: count }, (_, index) => {
    const position = (index / Math.max(1, count - 1)) * (values.length - 1)
    const lower = Math.floor(position)
    const upper = Math.min(values.length - 1, Math.ceil(position))
    const fraction = position - lower
    const lowerValue = Number(values[lower]) || 0
    const upperValue = Number(values[upper]) || 0
    return clamp(lowerValue * (1 - fraction) + upperValue * fraction, 0, 1)
  })
}

function cloneBands(values: Float32Array | null | undefined): Float32Array {
  const cloned = new Float32Array(AUDIO_SPECTRUM_BINS)
  if (!values?.length) {
    return cloned
  }
  cloned.set(values.subarray(0, Math.min(values.length, AUDIO_SPECTRUM_BINS)))
  return cloned
}

type BuildPreviewGpuAudioSignalFrameOptions = {
  features: AudioSpectrumFeatures | null
  frame: AudioSpectrumFrame | null
  reactiveEnergy: number
  spectrumBarCount: number
  timeSec: number
}

export function buildPreviewGpuAudioSignalFrame({
  features,
  frame,
  reactiveEnergy,
  spectrumBarCount,
  timeSec,
}: BuildPreviewGpuAudioSignalFrameOptions): PreviewGpuAudioSignalFrame | null {
  const baseRenderValues = frame?.renderValues ?? features?.energyBands ?? null
  if (!baseRenderValues?.length) {
    return null
  }

  const basePeakHoldValues = frame?.peakHoldValues ?? features?.peakHoldBands ?? baseRenderValues
  const renderValues = resampleValues(baseRenderValues, spectrumBarCount)
  const mirroredRenderValues = mirrorValues(renderValues)
  const peakHoldValues = resampleValues(basePeakHoldValues, spectrumBarCount)
  const mirroredPeakHoldValues = mirrorValues(peakHoldValues)

  return {
    timeSec,
    reactiveEnergy,
    kick: features?.kick ?? 0,
    drop: features?.drop ?? 0,
    averageEnergy: features?.averageEnergy ?? 0,
    averageTransient: features?.averageTransient ?? 0,
    averageOnset: features?.averageOnset ?? 0,
    styleMotionDrive: frame?.styleMotionDrive ?? 0,
    styleTriggerDrive: frame?.styleTriggerDrive ?? frame?.styleMotionDrive ?? 0,
    renderValues,
    mirroredRenderValues,
    peakHoldValues,
    mirroredPeakHoldValues,
    energyBands: cloneBands(features?.energyBands),
    peakHoldBands: cloneBands(features?.peakHoldBands),
    transientBands: cloneBands(features?.transientBands),
    onsetBands: cloneBands(features?.onsetBands),
  }
}
