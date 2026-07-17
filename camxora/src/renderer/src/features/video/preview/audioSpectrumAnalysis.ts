import { normalizeSpectrumStyleKey } from '@/features/video/domains/spectrum/spectrumLayerModel'

export const AUDIO_SPECTRUM_BINS = 64
const AUDIO_SAMPLE_RATE = 44100
const AUDIO_NYQUIST = AUDIO_SAMPLE_RATE / 2
const AUDIO_MIN_FREQ = 20
const AUDIO_MAX_FREQ = 12000
const AUDIO_MIN_LOG = Math.log10(AUDIO_MIN_FREQ)
const AUDIO_MAX_LOG = Math.log10(AUDIO_MAX_FREQ)
const SMOOTH_KERNEL = [0.1, 0.2, 0.4, 0.2, 0.1] as const
const FREQ_BOOST = Float32Array.from({ length: AUDIO_SPECTRUM_BINS }, (_, index) => {
  const normalized = index / AUDIO_SPECTRUM_BINS
  return 1 + normalized * normalized * 2
})

export type AudioSpectrumLogMapping = {
  idx1: Int32Array
  idx2: Int32Array
  frac: Float32Array
}

export type AudioSpectrumEnvelope = {
  bassFast: number
  bassSlow: number
  kick: number
  drop: number
  level: number
  peakHoldBands?: Float32Array | null
  energyBands: Float32Array | null
  slowBands: Float32Array | null
  floorBands: Float32Array | null
  transientBands: Float32Array | null
  onsetBands: Float32Array | null
  previousBands: Float32Array | null
}

export type AudioSpectrumFrame = {
  renderValues: Float32Array
  peakHoldValues?: Float32Array
  reactiveEnergy: number
  styleMotionDrive?: number
  styleTriggerDrive?: number
  sourceFeatures?: AudioSpectrumFeatures
}

export type AudioSpectrumFeatures = {
  energyBands: Float32Array
  peakHoldBands: Float32Array
  transientBands: Float32Array
  onsetBands: Float32Array
  framePeak: number
  averageEnergy: number
  averageTransient: number
  averageOnset: number
  level: number
  kick: number
  drop: number
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value))
}

function smoothstep01(value: number): number {
  const t = clamp(value, 0, 1)
  return t * t * (3 - 2 * t)
}

function averageValues(values: ArrayLike<number>, count = values.length): number {
  const safeCount = Math.max(0, Math.min(count, values.length))
  if (!safeCount) {
    return 0
  }

  let total = 0
  for (let index = 0; index < safeCount; index += 1) {
    total += values[index] ?? 0
  }
  return total / safeCount
}

export function createAudioSpectrumLogMapping(pointCount: number): AudioSpectrumLogMapping {
  const fftSizeHalf = Math.max(1, pointCount)
  const idx1 = new Int32Array(AUDIO_SPECTRUM_BINS)
  const idx2 = new Int32Array(AUDIO_SPECTRUM_BINS)
  const frac = new Float32Array(AUDIO_SPECTRUM_BINS)

  for (let index = 0; index < AUDIO_SPECTRUM_BINS; index += 1) {
    const logFreq =
      AUDIO_MIN_LOG + (index / AUDIO_SPECTRUM_BINS) * (AUDIO_MAX_LOG - AUDIO_MIN_LOG)
    const frequency = 10 ** logFreq
    const linearIndex = (frequency / AUDIO_NYQUIST) * fftSizeHalf
    const lower = Math.floor(linearIndex)
    const upper = Math.min(Math.ceil(linearIndex), fftSizeHalf - 1)
    idx1[index] = lower
    idx2[index] = upper
    frac[index] = linearIndex - lower
  }

  return { idx1, idx2, frac }
}

function mapFrequencyDataToPerceptualBands(
  frequencyData: Uint8Array,
  mapping: AudioSpectrumLogMapping,
): Float32Array {
  const result = new Float32Array(AUDIO_SPECTRUM_BINS)
  const upperBound = Math.max(0, frequencyData.length - 1)

  for (let index = 0; index < AUDIO_SPECTRUM_BINS; index += 1) {
    const lowerIndex = Math.min(mapping.idx1[index], upperBound)
    const upperIndex = Math.min(mapping.idx2[index], upperBound)
    const lowerValue = (frequencyData[lowerIndex] ?? 0) / 255
    const upperValue = (frequencyData[upperIndex] ?? 0) / 255
    const interpolated = lowerValue * (1 - mapping.frac[index]) + upperValue * mapping.frac[index]
    result[index] = clamp(interpolated * FREQ_BOOST[index], 0.01, 1)
  }

  return result
}

function smoothSpectrumValues(values: Float32Array): Float32Array {
  const smoothed = new Float32Array(values.length)

  for (let index = 0; index < values.length; index += 1) {
    let total = 0
    for (let offset = -2; offset <= 2; offset += 1) {
      const sourceIndex = clamp(index + offset, 0, values.length - 1)
      total += values[sourceIndex] * SMOOTH_KERNEL[offset + 2]
    }
    smoothed[index] = total
  }

  if (values.length >= 4) {
    smoothed[0] = values[0]
    smoothed[1] = values[1]
    smoothed[values.length - 2] = values[values.length - 2]
    smoothed[values.length - 1] = values[values.length - 1]
  }

  return smoothed
}

function smoothSpectrumValuesCrisp(values: Float32Array): Float32Array {
  const smoothed = new Float32Array(values.length)
  const kernel = [0.15, 0.7, 0.15] as const

  for (let index = 0; index < values.length; index += 1) {
    const left = values[clamp(index - 1, 0, values.length - 1)]
    const mid = values[index]
    const right = values[clamp(index + 1, 0, values.length - 1)]
    smoothed[index] = left * kernel[0] + mid * kernel[1] + right * kernel[2]
  }

  if (values.length >= 2) {
    smoothed[0] = values[0]
    smoothed[values.length - 1] = values[values.length - 1]
  }

  return smoothed
}

function extractAudioSpectrumFeatures(
  frequencyData: Uint8Array,
  inputGain: number,
  deltaSec: number,
  mapping: AudioSpectrumLogMapping,
  envelope: AudioSpectrumEnvelope,
): AudioSpectrumFeatures {
  const fftBands = mapFrequencyDataToPerceptualBands(frequencyData, mapping)
  const safeInputGain = clamp(inputGain, 0.1, 10)
  const scaledBands = new Float32Array(AUDIO_SPECTRUM_BINS)

  for (let index = 0; index < AUDIO_SPECTRUM_BINS; index += 1) {
    scaledBands[index] = clamp(fftBands[index] * safeInputGain, 0, 4)
  }

  if (!envelope.energyBands || envelope.energyBands.length !== AUDIO_SPECTRUM_BINS) {
    envelope.energyBands = new Float32Array(AUDIO_SPECTRUM_BINS)
  }
  if (!envelope.floorBands || envelope.floorBands.length !== AUDIO_SPECTRUM_BINS) {
    envelope.floorBands = new Float32Array(AUDIO_SPECTRUM_BINS)
  }
  if (!envelope.slowBands || envelope.slowBands.length !== AUDIO_SPECTRUM_BINS) {
    envelope.slowBands = new Float32Array(AUDIO_SPECTRUM_BINS)
  }
  if (!envelope.transientBands || envelope.transientBands.length !== AUDIO_SPECTRUM_BINS) {
    envelope.transientBands = new Float32Array(AUDIO_SPECTRUM_BINS)
  }
  if (!envelope.onsetBands || envelope.onsetBands.length !== AUDIO_SPECTRUM_BINS) {
    envelope.onsetBands = new Float32Array(AUDIO_SPECTRUM_BINS)
  }
  if (!envelope.previousBands || envelope.previousBands.length !== AUDIO_SPECTRUM_BINS) {
    envelope.previousBands = new Float32Array(AUDIO_SPECTRUM_BINS)
  }
  if (!envelope.peakHoldBands || envelope.peakHoldBands.length !== AUDIO_SPECTRUM_BINS) {
    envelope.peakHoldBands = new Float32Array(AUDIO_SPECTRUM_BINS)
  }

  const attackA = 1 - Math.exp(-deltaSec / 0.038)
  const releaseA = 1 - Math.exp(-deltaSec / 0.2)
  const slowA = 1 - Math.exp(-deltaSec / 0.34)
  const floorA = 1 - Math.exp(-deltaSec / 1.65)
  const transientAttackA = 1 - Math.exp(-deltaSec / 0.018)
  const transientReleaseA = 1 - Math.exp(-deltaSec / 0.075)
  const onsetAttackA = 1 - Math.exp(-deltaSec / 0.014)
  const onsetReleaseA = 1 - Math.exp(-deltaSec / 0.065)
  const energyBands = new Float32Array(AUDIO_SPECTRUM_BINS)
  const peakHoldBands = new Float32Array(AUDIO_SPECTRUM_BINS)
  const transientBands = new Float32Array(AUDIO_SPECTRUM_BINS)
  const onsetBands = new Float32Array(AUDIO_SPECTRUM_BINS)
  const peakHoldDecay = Math.exp(-deltaSec / 0.24)
  let framePeak = 0
  let averageEnergy = 0
  let averageTransient = 0
  let averageOnset = 0

  for (let index = 0; index < AUDIO_SPECTRUM_BINS; index += 1) {
    const previousEnergy = envelope.energyBands[index] ?? 0
    const nextValue = scaledBands[index]
    const energyMix = nextValue > previousEnergy ? attackA : releaseA
    const smoothedEnergy = previousEnergy * (1 - energyMix) + nextValue * energyMix
    envelope.energyBands[index] = smoothedEnergy

    const previousFloor = envelope.floorBands[index] ?? 0
    const trackedFloor = previousFloor * (1 - floorA) + smoothedEnergy * floorA
    envelope.floorBands[index] = trackedFloor

    const previousSlow = envelope.slowBands[index] ?? 0
    const trackedSlow = previousSlow * (1 - slowA) + smoothedEnergy * slowA
    envelope.slowBands[index] = trackedSlow

    const previousBand = envelope.previousBands[index] ?? 0
    const transientInput = Math.max(0, smoothedEnergy - previousBand)
    envelope.previousBands[index] = smoothedEnergy

    const previousTransient = envelope.transientBands[index] ?? 0
    const transientMix = transientInput > previousTransient ? transientAttackA : transientReleaseA
    const smoothedTransient = previousTransient * (1 - transientMix) + transientInput * transientMix
    envelope.transientBands[index] = smoothedTransient

    const onsetInput = Math.max(0, smoothedEnergy - trackedSlow)
    const previousOnset = envelope.onsetBands[index] ?? 0
    const onsetMix = onsetInput > previousOnset ? onsetAttackA : onsetReleaseA
    const smoothedOnset = previousOnset * (1 - onsetMix) + onsetInput * onsetMix
    envelope.onsetBands[index] = smoothedOnset

    const separatedEnergy = Math.max(0, smoothedEnergy - trackedFloor * 0.78)
    const nextPeakHold = Math.max(separatedEnergy, (envelope.peakHoldBands[index] ?? 0) * peakHoldDecay)
    envelope.peakHoldBands[index] = nextPeakHold
    energyBands[index] = separatedEnergy
    peakHoldBands[index] = nextPeakHold
    transientBands[index] = smoothedTransient
    onsetBands[index] = smoothedOnset
    framePeak = Math.max(framePeak, separatedEnergy + smoothedTransient * 0.68 + smoothedOnset * 0.82)
    averageEnergy += separatedEnergy
    averageTransient += smoothedTransient
    averageOnset += smoothedOnset
  }

  averageEnergy /= AUDIO_SPECTRUM_BINS
  averageTransient /= AUDIO_SPECTRUM_BINS
  averageOnset /= AUDIO_SPECTRUM_BINS

  const levelA = 1 - Math.exp(-deltaSec / 0.42)
  envelope.level = envelope.level * (1 - levelA) + framePeak * levelA

  const bassEnergy = averageValues(energyBands, 6)
  const lowMidEnergy = averageValues(energyBands.subarray(4, 12))
  const bassTransient = averageValues(transientBands, 6)
  const bassOnset = averageValues(onsetBands, 6)
  const kickFastA = 1 - Math.exp(-deltaSec / 0.055)
  const kickSlowA = 1 - Math.exp(-deltaSec / 0.28)
  const kickDecay = Math.exp(-deltaSec / 0.16)
  envelope.bassFast = envelope.bassFast * (1 - kickFastA) + (bassEnergy + bassTransient * 0.35) * kickFastA
  envelope.bassSlow = envelope.bassSlow * (1 - kickSlowA) + bassEnergy * kickSlowA
  const kickTrigger = Math.max(0, envelope.bassFast - envelope.bassSlow) + bassTransient * 0.4 + bassOnset * 0.62
  envelope.kick = Math.max(0, Math.max(kickTrigger, envelope.kick * kickDecay))

  const dropTrigger = clamp(bassEnergy * 0.68 + bassTransient * 0.74 + bassOnset * 0.42 - lowMidEnergy * 0.42, 0, 1.5)
  const dropAttackA = 1 - Math.exp(-deltaSec / 0.02)
  const dropReleaseA = 1 - Math.exp(-deltaSec / 0.082)
  const dropMix = dropTrigger > envelope.drop ? dropAttackA : dropReleaseA
  envelope.drop = envelope.drop * (1 - dropMix) + dropTrigger * dropMix

  return {
    energyBands,
    peakHoldBands,
    transientBands,
    onsetBands,
    framePeak,
    averageEnergy,
    averageTransient,
    averageOnset,
    level: envelope.level,
    kick: envelope.kick,
    drop: envelope.drop,
  }
}

function buildBaseRenderBands(
  features: AudioSpectrumFeatures,
  bandContrast: number,
  transientFocus: number,
  smoothingMode: 'smooth' | 'crisp',
): Float32Array {
  const normalizationMax = Math.max(0.0001, Math.max(features.framePeak, features.level))
  const normalizedContrast = clamp(bandContrast, 0.35, 5)
  const normalizedTransientFocus = clamp(transientFocus, 0.35, 4)
  const sustainWeight = 0.8 + (normalizedContrast - 1) * 0.1
  const transientWeight = 0.62 + (normalizedContrast - 1) * 0.2 + (normalizedTransientFocus - 1) * 0.34
  const onsetWeight = 0.34 + (normalizedContrast - 1) * 0.1 + (normalizedTransientFocus - 1) * 0.32
  const contrastCurve = clamp(1.06 - (normalizedContrast - 1) * 0.18, 0.68, 1.2)
  const floor = clamp((features.averageEnergy / normalizationMax) * (0.16 / normalizedContrast), 0.008, 0.08)
  const kickLift = clamp(features.kick, 0, 1.4) * 0.06
  const localAccentScale = 0.42 + (normalizedTransientFocus - 1) * 0.22
  const onsetAccentScale = 0.12 + (normalizedTransientFocus - 1) * 0.14
  const rawValues = new Float32Array(AUDIO_SPECTRUM_BINS)

  for (let index = 0; index < AUDIO_SPECTRUM_BINS; index += 1) {
    const energy = clamp(features.energyBands[index] / normalizationMax, 0, 1.4)
    const transient = clamp(features.transientBands[index] / normalizationMax, 0, 1.4)
    const onset = clamp(features.onsetBands[index] / normalizationMax, 0, 1.4)
    const combined = clamp(energy * sustainWeight + transient * transientWeight + onset * onsetWeight, 0, 1.75)
    rawValues[index] = combined
  }

  const smoothed = smoothingMode === 'crisp' ? smoothSpectrumValuesCrisp(rawValues) : smoothSpectrumValues(rawValues)
  const shaped = new Float32Array(AUDIO_SPECTRUM_BINS)

  for (let index = 0; index < AUDIO_SPECTRUM_BINS; index += 1) {
    const normalized = clamp(smoothed[index], 0, 1.6)
    const left = index > 0 ? clamp(smoothed[index - 1], 0, 1.6) : normalized
    const right = index + 1 < AUDIO_SPECTRUM_BINS ? clamp(smoothed[index + 1], 0, 1.6) : normalized
    const localPeak = Math.max(0, normalized - (left + right) * 0.5)
    const onset = clamp(features.onsetBands[index] / normalizationMax, 0, 1.2)
    const separated = clamp((normalized - floor) / Math.max(0.0001, 1 - floor), 0, 1)
    const curved = Math.pow(separated, contrastCurve)
    const bassWeight = 1 - Math.min(1, index / 12)
    shaped[index] = clamp(curved + localPeak * localAccentScale + Math.pow(onset, 0.92) * onsetAccentScale + bassWeight * kickLift, 0, 1)
  }

  return shaped
}

function expandRenderHeightRange(
  values: Float32Array,
  bandContrast: number,
  transientFocus: number,
): Float32Array {
  if (!values.length) {
    return values
  }

  let peak = 0
  for (let index = 0; index < values.length; index += 1) {
    peak = Math.max(peak, values[index] ?? 0)
  }
  if (peak <= 0.0001) {
    return values
  }

  const average = averageValues(values)
  const contrastDial = clamp(bandContrast, 0.35, 5)
  const transientDial = clamp(transientFocus, 0.35, 4)
  const targetPeak = clamp(0.8 + (contrastDial - 1) * 0.07 + (transientDial - 1) * 0.05, 0.76, 0.92)
  const gain = clamp(targetPeak / peak, 1.05, 3.2)
  const boostedAverage = average * gain
  const crestRange = Math.max(0.04, peak * gain - boostedAverage)
  const accentScale = 0.18 + (contrastDial - 1) * 0.16 + (transientDial - 1) * 0.24
  const crestCurve = clamp(0.94 - (contrastDial - 1) * 0.08 - (transientDial - 1) * 0.08, 0.64, 1)
  const expanded = new Float32Array(values.length)

  for (let index = 0; index < values.length; index += 1) {
    const lifted = clamp((values[index] ?? 0) * gain, 0, 1)
    const crest = clamp((lifted - boostedAverage) / crestRange, 0, 1)
    expanded[index] = clamp(lifted + Math.pow(crest, crestCurve) * accentScale, 0, 1)
  }

  return expanded
}

function applyStraightBarsStyle(
  baseValues: Float32Array,
  features: AudioSpectrumFeatures,
  bandContrast: number,
  kickImpact: number,
): { renderValues: Float32Array; peakHoldValues: Float32Array; reactiveEnergy: number } {
  const renderValues = baseValues.slice()
  const peakHoldValues = new Float32Array(baseValues.length)
  const contrastDial = clamp(bandContrast, 0.35, 5)
  const kickImpactDial = clamp(kickImpact, 0, 5)
  const averageEnergy = averageValues(renderValues)
  const contrast = 1.42 + clamp(features.averageEnergy * 1.1, 0, 0.42)
  const gate = clamp(averageEnergy * (0.34 - (contrastDial - 1) * 0.05) - features.kick * 0.028, 0.008, 0.105)
  const invRange = 1 / Math.max(0.0001, 1 - gate)
  const onsetScale = 0.12 + (contrastDial - 1) * 0.05

  for (let index = 0; index < renderValues.length; index += 1) {
    const gated = (renderValues[index] - gate) * invRange
    const onsetAccent = clamp(features.onsetBands[index] / Math.max(0.0001, features.framePeak), 0, 1) * onsetScale
    renderValues[index] = clamp(Math.pow(smoothstep01(gated), contrast * contrastDial) + onsetAccent, 0, 1)
    peakHoldValues[index] = clamp(features.peakHoldBands[index] / Math.max(0.0001, features.framePeak), 0, 1)
  }

  if (kickImpactDial > 0.001) {
    const transientLift = smoothstep01(features.drop * 0.92) * kickImpactDial
    for (let index = 0; index < renderValues.length; index += 1) {
      const normalizedIndex = index / Math.max(1, renderValues.length - 1)
      const wingProfile = Math.pow(Math.sin(normalizedIndex * Math.PI), 1.12)
      const edgeProfile = Math.pow(Math.abs(normalizedIndex - 0.5) * 2, 1.35)
      const bassWeight = 1 - Math.min(1, index / 10)
      const boost =
        transientLift *
        (0.08 + wingProfile * 0.24 + (1 - bassWeight) * 0.14 + edgeProfile * 0.06)
      renderValues[index] = clamp(renderValues[index] * (1 + boost), 0, 1)
    }
  }

  const reactiveEnergy = clamp(averageValues(renderValues) + features.kick * 0.34 + features.drop * kickImpactDial * 0.18, 0, 1)
  return { renderValues, peakHoldValues, reactiveEnergy }
}

function applyStyleWideKickAccent(
  renderValues: Float32Array,
  features: AudioSpectrumFeatures,
  styleFamily: string,
  kickImpact: number,
): void {
  const kickImpactDial = clamp(kickImpact, 0, 5)
  if (kickImpactDial <= 0.001) {
    return
  }

  const kickStart = smoothstep01(clamp((features.kick - 0.01) * (4.4 + kickImpactDial * 0.85), 0, 1.4))
  const dropDrive = smoothstep01(clamp((features.drop - 0.012) * (3.2 + kickImpactDial * 0.75), 0, 1.4))
  const flareDrive = clamp(kickStart * 0.52 + dropDrive * (0.42 + kickImpactDial * 0.24), 0, 1)
  if (flareDrive <= 0.0001) {
    return
  }

  const styleScale =
    styleFamily === 'orbital-bars'
      ? 0.22
      : styleFamily === 'dot-matrix'
        ? 0.18
        : styleFamily === 'wave-ribbon'
          ? 0.24
          : styleFamily === 'liquid-mass'
            ? 0.26
            : styleFamily === 'halo-stack'
              ? 0.22
              : 0.2

  for (let index = 0; index < renderValues.length; index += 1) {
    const normalizedIndex = index / Math.max(1, renderValues.length - 1)
    const bassWeight = 1 - Math.min(1, index / 12)
    const centerBias = 1 - Math.abs(normalizedIndex - 0.5) / 0.5
    const left = index > 0 ? renderValues[index - 1] ?? renderValues[index] ?? 0 : renderValues[index] ?? 0
    const mid = renderValues[index] ?? 0
    const right =
      index + 1 < renderValues.length ? renderValues[index + 1] ?? renderValues[index] ?? 0 : renderValues[index] ?? 0
    const localPeak = Math.max(0, mid - (left + right) * 0.5)
    const familyBias =
      styleFamily === 'orbital-bars'
        ? 0.5 + centerBias * 0.28
        : styleFamily === 'wave-ribbon'
          ? 0.62 + centerBias * 0.18
          : styleFamily === 'liquid-mass'
            ? 0.78 + bassWeight * 0.24
            : styleFamily === 'halo-stack'
              ? 0.56 + centerBias * 0.24
              : 0.58 + localPeak * 0.26
    const boost =
      flareDrive * styleScale * (0.3 + bassWeight * 0.72 + familyBias * 0.34 + Math.pow(localPeak, 0.82) * 0.48)
    renderValues[index] = clamp(mid * (1 + boost) + flareDrive * styleScale * bassWeight * 0.08, 0, 1)
  }
}

function applyFlyingGlowStyle(
  baseValues: Float32Array,
  features: AudioSpectrumFeatures,
  kickImpact: number,
): {
  renderValues: Float32Array
  peakHoldValues: Float32Array
  reactiveEnergy: number
  styleMotionDrive: number
  styleTriggerDrive: number
} {
  const renderValues = baseValues.slice()
  const peakHoldValues = new Float32Array(baseValues.length)
  const kickImpactDial = clamp(kickImpact, 0, 5)
  const kickStart = smoothstep01(clamp((features.kick - 0.015) * (8.4 + kickImpactDial * 0.8), 0, 1.45))
  const dropDrive = Math.pow(
    smoothstep01(clamp((features.drop - 0.02) * (4.1 + kickImpactDial * 0.92), 0, 1.4)),
    0.9,
  )
  const bassEnergy = averageValues(features.energyBands, 8)
  const bassOnset = averageValues(features.onsetBands, 8)
  const bassTextureDrive = smoothstep01(
    clamp((bassEnergy * 0.94 + bassOnset * 1.18 - 0.06) * (1.55 + kickImpactDial * 0.24), 0, 1.35),
  )
  const wingPulse = clamp(Math.max(kickStart, dropDrive * (0.9 + kickImpactDial * 0.34)), 0, 1)
  const wingDrive = clamp(Math.max(wingPulse, bassTextureDrive * 0.6), 0, 1)
  const waveformBedEnergy = smoothstep01(clamp(features.level * 1.05 + bassTextureDrive * 0.16, 0, 1.3))

  for (let index = 0; index < renderValues.length; index += 1) {
    const normalizedIndex = index / Math.max(1, renderValues.length - 1)
    const leftShoulder = Math.exp(-(((normalizedIndex - 0.18) / 0.16) ** 2))
    const rightShoulder = Math.exp(-(((normalizedIndex - 0.82) / 0.16) ** 2))
    const shoulderBias = Math.max(leftShoulder, rightShoulder)
    const centerDip = Math.exp(-(((normalizedIndex - 0.5) / 0.18) ** 2))
    const wingBias = clamp(0.16 + shoulderBias * 0.72 - centerDip * 0.12, 0.05, 1.08)
    const restFloor = 0.0035
    const onsetTexture = clamp(features.onsetBands[index] / Math.max(0.0001, features.framePeak), 0, 1) * 0.095
    const transientTexture =
      clamp(features.transientBands[index] / Math.max(0.0001, features.framePeak), 0, 1) * 0.09
    const circularWave =
      Math.pow(renderValues[index], 0.9) * (0.17 + waveformBedEnergy * 0.11) +
      onsetTexture +
      transientTexture
    const bassBedLift = bassTextureDrive * (0.08 + wingBias * 0.12)
    const bigBeatLift = 0.82 + Math.pow(wingPulse, 1.7) * (0.42 + kickImpactDial * 0.08)
    const kickSpike =
      wingBias *
      (0.105 +
        Math.pow(renderValues[index], 0.82) * 0.64 +
        features.drop * 0.16 +
        features.kick * 0.1 +
        bassBedLift) *
      Math.pow(wingDrive, 1.3) *
      bigBeatLift
    renderValues[index] = clamp(restFloor + circularWave + kickSpike, 0, 1)
    peakHoldValues[index] = clamp(features.peakHoldBands[index] / Math.max(0.0001, features.framePeak), 0, 1)
  }

  const smoothedWing = smoothSpectrumValues(renderValues)
  for (let index = 0; index < renderValues.length; index += 1) {
    renderValues[index] = clamp(smoothedWing[index] * 0.74 + renderValues[index] * 0.26, 0, 1)
  }

  const averageEnergy = averageValues(renderValues)
  const reactiveEnergy = clamp(
    averageEnergy * 0.3 +
      smoothstep01(clamp(features.level * 0.78, 0, 1.12)) * 0.05 +
      features.kick * 0.82 +
      features.drop * (0.66 + kickImpactDial * 0.34),
    0,
    1,
  )
  const styleMotionDrive = wingDrive
  const styleTriggerDrive = wingPulse
  return { renderValues, peakHoldValues, reactiveEnergy, styleMotionDrive, styleTriggerDrive }
}

function applyGenericStyle(
  baseValues: Float32Array,
  features: AudioSpectrumFeatures,
  styleFamily: string,
  kickImpact: number,
): { renderValues: Float32Array; peakHoldValues: Float32Array; reactiveEnergy: number } {
  const normalizedStyle = normalizeSpectrumStyleKey(styleFamily)
  const renderValues = baseValues.slice()
  const peakHoldValues = new Float32Array(baseValues.length)
  const kickImpactDial = clamp(kickImpact, 0, 5)

  if (normalizedStyle === 'orbital-bars') {
    for (let index = 0; index < renderValues.length; index += 1) {
      const sparkle =
        clamp(features.transientBands[index] / Math.max(0.0001, features.framePeak), 0, 1) * 0.18 +
        clamp(features.onsetBands[index] / Math.max(0.0001, features.framePeak), 0, 1) * 0.18
      renderValues[index] = clamp(renderValues[index] + sparkle, 0, 1)
    }
  } else if (normalizedStyle === 'dot-matrix') {
    for (let index = 0; index < renderValues.length; index += 1) {
      const onsetPunch = clamp(features.onsetBands[index] / Math.max(0.0001, features.framePeak), 0, 1) * 0.2
      renderValues[index] = clamp(Math.pow(renderValues[index], 0.94) + onsetPunch, 0, 1)
    }
  } else if (normalizedStyle === 'halo-stack' || normalizedStyle === 'wave-ribbon') {
    for (let index = 0; index < renderValues.length; index += 1) {
      const onsetGlow = clamp(features.onsetBands[index] / Math.max(0.0001, features.framePeak), 0, 1) * 0.1
      renderValues[index] = clamp(Math.pow(renderValues[index], 0.92) + onsetGlow, 0, 1)
    }
  } else if (normalizedStyle === 'liquid-mass') {
    for (let index = 0; index < renderValues.length; index += 1) {
      const onsetRipple = clamp(features.onsetBands[index] / Math.max(0.0001, features.framePeak), 0, 1) * 0.08
      renderValues[index] = clamp(Math.pow(renderValues[index], 0.88) + onsetRipple, 0, 1)
    }
  } else {
    for (let index = 0; index < renderValues.length; index += 1) {
      const onsetLift = clamp(features.onsetBands[index] / Math.max(0.0001, features.framePeak), 0, 1) * 0.08
      renderValues[index] = clamp(renderValues[index] + onsetLift, 0, 1)
    }
  }

  applyStyleWideKickAccent(renderValues, features, normalizedStyle, kickImpact)

  for (let index = 0; index < renderValues.length; index += 1) {
    peakHoldValues[index] = clamp(features.peakHoldBands[index] / Math.max(0.0001, features.framePeak), 0, 1)
  }

  const reactiveEnergy = clamp(
    averageValues(renderValues) +
      features.kick * 0.26 +
      features.drop * (0.1 + kickImpactDial * 0.1) +
      features.averageTransient * 0.16 +
      features.averageOnset * 0.12,
    0,
    1,
  )

  return { renderValues, peakHoldValues, reactiveEnergy }
}

function beautifySpectrumFrame(
  styledFrame: AudioSpectrumFrame,
  features: AudioSpectrumFeatures,
  barHeight: number,
  bassEmphasis: number,
  trebleShimmer: number,
  peakHoldBlend: number,
): AudioSpectrumFrame {
  const heightDial = clamp(barHeight, 0.5, 6)
  const bassDial = clamp(bassEmphasis, 0.35, 4)
  const trebleDial = clamp(trebleShimmer, 0.35, 4)
  const holdDial = clamp(peakHoldBlend, 0, 1)

  if (
    Math.abs(heightDial - 1) <= 0.0001 &&
    Math.abs(bassDial - 1) <= 0.0001 &&
    Math.abs(trebleDial - 1) <= 0.0001 &&
    holdDial <= 0.0001
  ) {
    return styledFrame
  }

  const normalizationMax = Math.max(0.0001, features.framePeak)
  const renderValues = styledFrame.renderValues.slice()
  const peakHoldValues = styledFrame.peakHoldValues ?? new Float32Array(renderValues.length)

  for (let index = 0; index < renderValues.length; index += 1) {
    const normalizedIndex = index / Math.max(1, renderValues.length - 1)
    const bassWeight = Math.pow(1 - Math.min(1, normalizedIndex / 0.32), 1.15)
    const trebleWeight = Math.pow(Math.max(0, (normalizedIndex - 0.42) / 0.58), 0.92)
    const transientLift =
      clamp(features.transientBands[index] / normalizationMax, 0, 1) * (0.06 + trebleWeight * 0.14)
    const onsetLift =
      clamp(features.onsetBands[index] / normalizationMax, 0, 1) * (0.04 + trebleWeight * 0.12)
    const peakTail =
      Math.max(0, peakHoldValues[index] - renderValues[index]) *
      holdDial *
      (0.34 + bassWeight * 0.12 + trebleWeight * 0.16)
    const bassScale =
      bassDial >= 1
        ? 1 + (bassDial - 1) * bassWeight * (0.16 + features.kick * 0.09 + features.drop * 0.07)
        : 1 - (1 - bassDial) * bassWeight * 0.22
    const trebleScale =
      trebleDial >= 1
        ? 1 + (trebleDial - 1) * trebleWeight * 0.2
        : 1 - (1 - trebleDial) * trebleWeight * 0.18
    const shimmer = Math.max(0, trebleDial - 1) * (transientLift + onsetLift)

    renderValues[index] = clamp(
      (renderValues[index] * bassScale * trebleScale + peakTail + shimmer) * heightDial,
      0,
      1,
    )
  }

  const reactiveEnergy = clamp(
    Math.max(
      styledFrame.reactiveEnergy,
      averageValues(renderValues) +
        Math.max(0, heightDial - 1) * 0.06 +
        features.kick * 0.12 +
        features.drop * 0.08 +
        Math.max(0, bassDial - 1) * 0.03 +
        Math.max(0, trebleDial - 1) * 0.02,
    ),
    0,
    1,
  )

  return {
    ...styledFrame,
    renderValues,
    reactiveEnergy,
  }
}

export function buildAudioSpectrumFrameFromFeatures(
  features: AudioSpectrumFeatures,
  bandContrast: number,
  transientFocus: number,
  kickImpact: number,
  styleFamily: string,
  barHeight = 1,
  bassEmphasis = 1,
  trebleShimmer = 1,
  peakHoldBlend = 0,
): AudioSpectrumFrame {
  const normalizedStyle = normalizeSpectrumStyleKey(styleFamily)
  const smoothingMode =
    normalizedStyle === 'straight-bars' || normalizedStyle === 'orbital-bars' || normalizedStyle === 'dot-matrix'
      ? 'crisp'
      : 'smooth'
  const baseValues = expandRenderHeightRange(
    buildBaseRenderBands(features, bandContrast, transientFocus, smoothingMode),
    bandContrast,
    transientFocus,
  )

  const styledFrame =
    normalizedStyle === 'straight-bars'
      ? applyStraightBarsStyle(baseValues, features, bandContrast, kickImpact)
      : normalizedStyle === 'flying-glow'
        ? applyFlyingGlowStyle(baseValues, features, kickImpact)
        : applyGenericStyle(baseValues, features, normalizedStyle, kickImpact)

  return beautifySpectrumFrame({
    ...styledFrame,
    sourceFeatures: features,
  }, features, barHeight, bassEmphasis, trebleShimmer, peakHoldBlend)
}

export function analyseAudioSpectrumFrame(
  frequencyData: Uint8Array | null,
  inputGain: number,
  bandContrast: number,
  transientFocus: number,
  kickImpact: number,
  deltaSec: number,
  mapping: AudioSpectrumLogMapping | null,
  envelope: AudioSpectrumEnvelope,
  styleFamily: string,
  barHeight = 1,
  bassEmphasis = 1,
  trebleShimmer = 1,
  peakHoldBlend = 0,
): AudioSpectrumFrame | null {
  if (!frequencyData?.length || !mapping) {
    return null
  }

  const features = extractAudioSpectrumFeatures(frequencyData, inputGain, deltaSec, mapping, envelope)
  return buildAudioSpectrumFrameFromFeatures(
    features,
    bandContrast,
    transientFocus,
    kickImpact,
    styleFamily,
    barHeight,
    bassEmphasis,
    trebleShimmer,
    peakHoldBlend,
  )
}
