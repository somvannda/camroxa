import {
  AUDIO_SPECTRUM_BINS,
  type AudioSpectrumFeatures,
} from '@/features/video/preview/audioSpectrumAnalysis'

const AUDIO_MIN_FREQ = 20
const AUDIO_MAX_FREQ = 12000
const AUDIO_MIN_LOG = Math.log10(AUDIO_MIN_FREQ)
const FREQ_BOOST = Float32Array.from({ length: AUDIO_SPECTRUM_BINS }, (_, index) => {
  const normalized = index / AUDIO_SPECTRUM_BINS
  return 1 + normalized * normalized * 2
})

export type PreviewAudioReactiveFeatureFrame = AudioSpectrumFeatures & {
  timeSec: number
  reactiveEnergy: number
  bass: number
  mid: number
  treble: number
  energy: number
  onset: number
  transient: number
  beat: number
}

export type PreviewAudioReactiveFeatureTimeline = {
  durationSec: number
  frameRate: number
  frames: ReadonlyArray<PreviewAudioReactiveFeatureFrame>
}

export type PreviewAudioReactiveFeatureSample = PreviewAudioReactiveFeatureFrame

export type SerializedPreviewAudioReactiveFeatureFrame = Omit<
  PreviewAudioReactiveFeatureFrame,
  'energyBands' | 'peakHoldBands' | 'transientBands' | 'onsetBands'
> & {
  energyBands: number[]
  peakHoldBands: number[]
  transientBands: number[]
  onsetBands: number[]
}

export type SerializedPreviewAudioReactiveFeatureTimeline = {
  durationSec: number
  frameRate: number
  frames: SerializedPreviewAudioReactiveFeatureFrame[]
}

type BuildPreviewAudioReactiveFeatureTimelineOptions = {
  channelData: ReadonlyArray<Float32Array>
  sampleRate: number
  durationSec: number
  frameRate?: number
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value))
}

function lerp(start: number, end: number, mixAmount: number): number {
  return start + (end - start) * mixAmount
}

function mixdownChannels(channelData: ReadonlyArray<Float32Array>): Float32Array {
  const length = channelData[0]?.length ?? 0
  const mono = new Float32Array(length)
  if (!length || !channelData.length) {
    return mono
  }

  for (let channelIndex = 0; channelIndex < channelData.length; channelIndex += 1) {
    const channel = channelData[channelIndex]
    for (let sampleIndex = 0; sampleIndex < length; sampleIndex += 1) {
      mono[sampleIndex] += channel[sampleIndex] ?? 0
    }
  }

  const scale = 1 / channelData.length
  for (let sampleIndex = 0; sampleIndex < length; sampleIndex += 1) {
    mono[sampleIndex] *= scale
  }
  return mono
}

function downsampleSignal(input: Float32Array, factor: number): Float32Array {
  if (factor <= 1) {
    return input
  }

  const length = Math.ceil(input.length / factor)
  const output = new Float32Array(length)
  for (let index = 0; index < length; index += 1) {
    let total = 0
    let count = 0
    for (let sampleOffset = 0; sampleOffset < factor; sampleOffset += 1) {
      const sourceIndex = index * factor + sampleOffset
      if (sourceIndex >= input.length) {
        break
      }
      total += input[sourceIndex] ?? 0
      count += 1
    }
    output[index] = count ? total / count : 0
  }
  return output
}

function applyOnePoleLowpass(
  input: Float32Array,
  sampleRate: number,
  cutoffHz: number,
): Float32Array {
  const output = new Float32Array(input.length)
  if (!input.length) {
    return output
  }

  const clampedCutoff = clamp(cutoffHz, 10, Math.max(20, sampleRate * 0.45))
  const rc = 1 / (Math.PI * 2 * clampedCutoff)
  const dt = 1 / Math.max(1, sampleRate)
  const alpha = dt / (rc + dt)
  let previous = input[0] ?? 0

  for (let index = 0; index < input.length; index += 1) {
    previous += ((input[index] ?? 0) - previous) * alpha
    output[index] = previous
  }

  return output
}

function computeWindowRms(input: Float32Array, startIndex: number, endIndex: number): number {
  const safeStart = clamp(startIndex, 0, input.length)
  const safeEnd = clamp(endIndex, safeStart + 1, input.length)
  let total = 0
  for (let index = safeStart; index < safeEnd; index += 1) {
    const sample = input[index] ?? 0
    total += sample * sample
  }
  return Math.sqrt(total / Math.max(1, safeEnd - safeStart))
}

function normalizeSeries(values: number[]): number[] {
  let maxValue = 0
  for (const value of values) {
    maxValue = Math.max(maxValue, value)
  }
  if (maxValue <= 0.000001) {
    return values.map(() => 0)
  }
  return values.map((value) => clamp(value / maxValue, 0, 1))
}

function buildLogBandFrequencies(sampleRate: number): Float32Array {
  const nyquist = sampleRate / 2
  const maxFrequency = Math.min(AUDIO_MAX_FREQ, nyquist * 0.92)
  const maxLog = Math.log10(Math.max(AUDIO_MIN_FREQ + 1, maxFrequency))
  return Float32Array.from({ length: AUDIO_SPECTRUM_BINS }, (_, index) => {
    const logFreq = AUDIO_MIN_LOG + (index / AUDIO_SPECTRUM_BINS) * (maxLog - AUDIO_MIN_LOG)
    return 10 ** logFreq
  })
}

function computeLogBandMagnitudes(
  samples: Float32Array,
  sampleRate: number,
  frequencies: Float32Array,
): Float32Array {
  const magnitudes = new Float32Array(frequencies.length)
  if (!samples.length) {
    return magnitudes
  }

  const windowed = new Float32Array(samples.length)
  for (let index = 0; index < samples.length; index += 1) {
    const hann = 0.5 * (1 - Math.cos((Math.PI * 2 * index) / Math.max(1, samples.length - 1)))
    windowed[index] = (samples[index] ?? 0) * hann
  }

  for (let bandIndex = 0; bandIndex < frequencies.length; bandIndex += 1) {
    const targetFrequency = frequencies[bandIndex]
    const omega = (Math.PI * 2 * targetFrequency) / sampleRate
    const coefficient = 2 * Math.cos(omega)
    let q0 = 0
    let q1 = 0
    let q2 = 0

    for (let sampleIndex = 0; sampleIndex < windowed.length; sampleIndex += 1) {
      q0 = coefficient * q1 - q2 + (windowed[sampleIndex] ?? 0)
      q2 = q1
      q1 = q0
    }

    const power = q1 * q1 + q2 * q2 - coefficient * q1 * q2
    magnitudes[bandIndex] = Math.sqrt(Math.max(0, power)) / Math.max(1, windowed.length)
  }

  return magnitudes
}

export function buildPreviewAudioReactiveFeatureTimeline({
  channelData,
  sampleRate,
  durationSec,
  frameRate = 30,
}: BuildPreviewAudioReactiveFeatureTimelineOptions): PreviewAudioReactiveFeatureTimeline {
  const mono = mixdownChannels(channelData)
  const downsampleFactor = sampleRate >= 44_000 ? 2 : 1
  const analysisSampleRate = Math.max(11_025, Math.round(sampleRate / downsampleFactor))
  const analysisMono = downsampleSignal(mono, downsampleFactor)
  const safeDurationSec = Math.max(
    0,
    Number.isFinite(durationSec) ? durationSec : mono.length / Math.max(1, sampleRate),
  )
  const safeFrameRate = clamp(Math.round(frameRate || 30), 24, 120)
  const frameCount = Math.max(1, Math.ceil(safeDurationSec * safeFrameRate) + 1)
  const hopSize = Math.max(1, Math.round(analysisSampleRate / safeFrameRate))
  const windowSize = Math.max(256, Math.min(analysisMono.length || 256, hopSize * 8))
  const bandFrequencies = buildLogBandFrequencies(analysisSampleRate)

  const bassLowpass = applyOnePoleLowpass(analysisMono, analysisSampleRate, 180)
  const midBoundaryLowpass = applyOnePoleLowpass(analysisMono, analysisSampleRate, 2500)
  const bassSignal = bassLowpass
  const midSignal = new Float32Array(analysisMono.length)
  const trebleSignal = new Float32Array(analysisMono.length)

  for (let index = 0; index < analysisMono.length; index += 1) {
    midSignal[index] = (midBoundaryLowpass[index] ?? 0) - (bassSignal[index] ?? 0)
    trebleSignal[index] = (analysisMono[index] ?? 0) - (midBoundaryLowpass[index] ?? 0)
  }

  const rawEnergy = new Array<number>(frameCount).fill(0)
  const rawBass = new Array<number>(frameCount).fill(0)
  const rawMid = new Array<number>(frameCount).fill(0)
  const rawTreble = new Array<number>(frameCount).fill(0)
  const rawBandFrames = new Array<Float32Array>(frameCount)
  let globalBandPeak = 0

  for (let frameIndex = 0; frameIndex < frameCount; frameIndex += 1) {
    const start = Math.min(analysisMono.length, frameIndex * hopSize)
    const end = Math.min(analysisMono.length, start + windowSize)
    rawEnergy[frameIndex] = computeWindowRms(analysisMono, start, end)
    rawBass[frameIndex] = computeWindowRms(bassSignal, start, end)
    rawMid[frameIndex] = computeWindowRms(midSignal, start, end)
    rawTreble[frameIndex] = computeWindowRms(trebleSignal, start, end)

    const bandMagnitudes = computeLogBandMagnitudes(
      analysisMono.subarray(start, end),
      analysisSampleRate,
      bandFrequencies,
    )
    rawBandFrames[frameIndex] = bandMagnitudes
    for (let bandIndex = 0; bandIndex < bandMagnitudes.length; bandIndex += 1) {
      globalBandPeak = Math.max(globalBandPeak, bandMagnitudes[bandIndex] ?? 0)
    }
  }

  const normalizedEnergy = normalizeSeries(rawEnergy)
  const normalizedBass = normalizeSeries(rawBass)
  const normalizedMid = normalizeSeries(rawMid)
  const normalizedTreble = normalizeSeries(rawTreble)
  const frames: PreviewAudioReactiveFeatureFrame[] = new Array(frameCount)
  const deltaSec = 1 / safeFrameRate

  const energyAvgAlpha = 1 - Math.exp(-deltaSec / 0.22)
  const bassAvgAlpha = 1 - Math.exp(-deltaSec / 0.28)
  const kickFastAlpha = 1 - Math.exp(-deltaSec / 0.045)
  const kickSlowAlpha = 1 - Math.exp(-deltaSec / 0.22)
  const dropAttackAlpha = 1 - Math.exp(-deltaSec / 0.02)
  const dropReleaseAlpha = 1 - Math.exp(-deltaSec / 0.09)
  const peakDecay = Math.exp(-deltaSec / 0.26)

  const attackA = 1 - Math.exp(-deltaSec / 0.038)
  const releaseA = 1 - Math.exp(-deltaSec / 0.2)
  const slowA = 1 - Math.exp(-deltaSec / 0.34)
  const floorA = 1 - Math.exp(-deltaSec / 1.65)
  const transientAttackA = 1 - Math.exp(-deltaSec / 0.018)
  const transientReleaseA = 1 - Math.exp(-deltaSec / 0.075)
  const onsetAttackA = 1 - Math.exp(-deltaSec / 0.014)
  const onsetReleaseA = 1 - Math.exp(-deltaSec / 0.065)

  let energyAverage = normalizedEnergy[0] ?? 0
  let bassAverage = normalizedBass[0] ?? 0
  let kickFast = normalizedBass[0] ?? 0
  let kickSlow = normalizedBass[0] ?? 0
  let drop = 0
  let lastEnergy = normalizedEnergy[0] ?? 0
  let lastBeatTimeSec = -1

  const smoothedEnergyBands = new Float32Array(AUDIO_SPECTRUM_BINS)
  const floorBands = new Float32Array(AUDIO_SPECTRUM_BINS)
  const slowBands = new Float32Array(AUDIO_SPECTRUM_BINS)
  const previousBands = new Float32Array(AUDIO_SPECTRUM_BINS)
  const transientStateBands = new Float32Array(AUDIO_SPECTRUM_BINS)
  const onsetStateBands = new Float32Array(AUDIO_SPECTRUM_BINS)
  const peakHoldStateBands = new Float32Array(AUDIO_SPECTRUM_BINS)

  for (let frameIndex = 0; frameIndex < frameCount; frameIndex += 1) {
    const energy = normalizedEnergy[frameIndex] ?? 0
    const bass = normalizedBass[frameIndex] ?? 0
    const mid = normalizedMid[frameIndex] ?? 0
    const treble = normalizedTreble[frameIndex] ?? 0
    const transient = clamp(energy - lastEnergy, 0, 1)
    lastEnergy = energy

    energyAverage += (energy - energyAverage) * energyAvgAlpha
    bassAverage += (bass - bassAverage) * bassAvgAlpha
    const onset = clamp(energy - energyAverage, 0, 1)
    const bassRise = clamp(bass - bassAverage, 0, 1)

    kickFast += (bass + transient * 0.22 - kickFast) * kickFastAlpha
    kickSlow += (bass - kickSlow) * kickSlowAlpha
    const kickRaw = clamp(
      Math.max(0, kickFast - kickSlow) + bassRise * 0.78 + onset * 0.58 + transient * 0.36,
      0,
      1.6,
    )
    const kick = clamp(Math.max(kickRaw, (frames[frameIndex - 1]?.kick ?? 0) * peakDecay), 0, 1)

    const dropRaw = clamp(bass * 0.68 + transient * 0.74 + onset * 0.42 - mid * 0.32, 0, 1.5)
    const dropMix = dropRaw > drop ? dropAttackAlpha : dropReleaseAlpha
    drop += (dropRaw - drop) * dropMix

    const timeSec = frameIndex / safeFrameRate
    const beatThreshold = 0.34
    const minBeatIntervalSec = 0.18
    const beatReady = lastBeatTimeSec < 0 || timeSec - lastBeatTimeSec >= minBeatIntervalSec
    const beat = beatReady && kickRaw >= beatThreshold ? 1 : 0
    if (beat > 0.5) {
      lastBeatTimeSec = timeSec
    }

    const rawBandMagnitudes = rawBandFrames[frameIndex]
    const energyBands = new Float32Array(AUDIO_SPECTRUM_BINS)
    const transientBands = new Float32Array(AUDIO_SPECTRUM_BINS)
    const onsetBands = new Float32Array(AUDIO_SPECTRUM_BINS)
    const peakHoldBands = new Float32Array(AUDIO_SPECTRUM_BINS)
    let framePeak = 0
    let averageEnergy = 0
    let averageTransient = 0
    let averageOnset = 0

    for (let bandIndex = 0; bandIndex < AUDIO_SPECTRUM_BINS; bandIndex += 1) {
      const magnitude = clamp(
        ((rawBandMagnitudes?.[bandIndex] ?? 0) / Math.max(0.000001, globalBandPeak)) * FREQ_BOOST[bandIndex],
        0,
        2.5,
      )
      const previousEnergyBand = smoothedEnergyBands[bandIndex] ?? 0
      const energyMix = magnitude > previousEnergyBand ? attackA : releaseA
      const smoothedBand = previousEnergyBand * (1 - energyMix) + magnitude * energyMix
      smoothedEnergyBands[bandIndex] = smoothedBand

      const trackedFloor = (floorBands[bandIndex] ?? 0) * (1 - floorA) + smoothedBand * floorA
      floorBands[bandIndex] = trackedFloor

      const trackedSlow = (slowBands[bandIndex] ?? 0) * (1 - slowA) + smoothedBand * slowA
      slowBands[bandIndex] = trackedSlow

      const transientInput = Math.max(0, smoothedBand - (previousBands[bandIndex] ?? 0))
      previousBands[bandIndex] = smoothedBand

      const previousTransient = transientStateBands[bandIndex] ?? 0
      const transientMix = transientInput > previousTransient ? transientAttackA : transientReleaseA
      const smoothedTransient = previousTransient * (1 - transientMix) + transientInput * transientMix
      transientStateBands[bandIndex] = smoothedTransient

      const onsetInput = Math.max(0, smoothedBand - trackedSlow)
      const previousOnset = onsetStateBands[bandIndex] ?? 0
      const onsetMix = onsetInput > previousOnset ? onsetAttackA : onsetReleaseA
      const smoothedOnset = previousOnset * (1 - onsetMix) + onsetInput * onsetMix
      onsetStateBands[bandIndex] = smoothedOnset

      const separatedEnergy = Math.max(0, smoothedBand - trackedFloor * 0.78)
      const nextPeakHold = Math.max(separatedEnergy, (peakHoldStateBands[bandIndex] ?? 0) * peakDecay)
      peakHoldStateBands[bandIndex] = nextPeakHold

      energyBands[bandIndex] = separatedEnergy
      transientBands[bandIndex] = smoothedTransient
      onsetBands[bandIndex] = smoothedOnset
      peakHoldBands[bandIndex] = nextPeakHold
      framePeak = Math.max(framePeak, separatedEnergy + smoothedTransient * 0.68 + smoothedOnset * 0.82)
      averageEnergy += separatedEnergy
      averageTransient += smoothedTransient
      averageOnset += smoothedOnset
    }

    averageEnergy /= AUDIO_SPECTRUM_BINS
    averageTransient /= AUDIO_SPECTRUM_BINS
    averageOnset /= AUDIO_SPECTRUM_BINS
    const reactiveEnergy = clamp(
      averageEnergy * 0.38 +
        kick * 0.22 +
        clamp(drop, 0, 1) * 0.2 +
        averageOnset * 0.1 +
        averageTransient * 0.1,
      0,
      1,
    )

    frames[frameIndex] = {
      timeSec,
      energyBands,
      peakHoldBands,
      transientBands,
      onsetBands,
      framePeak,
      averageEnergy,
      averageTransient,
      averageOnset,
      level: Math.max(framePeak, energy),
      kick,
      drop: clamp(drop, 0, 1),
      reactiveEnergy,
      bass,
      mid,
      treble,
      energy,
      onset,
      transient,
      beat,
    }
  }

  return {
    durationSec: safeDurationSec,
    frameRate: safeFrameRate,
    frames,
  }
}

export function buildPreviewAudioReactiveFeatureTimelineFromAudioBuffer(
  audioBuffer: AudioBuffer,
  frameRate = 30,
): PreviewAudioReactiveFeatureTimeline {
  const channels = Array.from({ length: audioBuffer.numberOfChannels }, (_, index) =>
    audioBuffer.getChannelData(index),
  )
  return buildPreviewAudioReactiveFeatureTimeline({
    channelData: channels,
    sampleRate: audioBuffer.sampleRate,
    durationSec: audioBuffer.duration,
    frameRate,
  })
}

export function serializePreviewAudioReactiveFeatureTimeline(
  timeline: PreviewAudioReactiveFeatureTimeline,
): SerializedPreviewAudioReactiveFeatureTimeline {
  return {
    durationSec: timeline.durationSec,
    frameRate: timeline.frameRate,
    frames: timeline.frames.map((frame) => ({
      ...frame,
      energyBands: Array.from(frame.energyBands),
      peakHoldBands: Array.from(frame.peakHoldBands),
      transientBands: Array.from(frame.transientBands),
      onsetBands: Array.from(frame.onsetBands),
    })),
  }
}

export function deserializePreviewAudioReactiveFeatureTimeline(
  timeline: SerializedPreviewAudioReactiveFeatureTimeline | null,
): PreviewAudioReactiveFeatureTimeline | null {
  if (!timeline || !Array.isArray(timeline.frames)) {
    return null
  }

  return {
    durationSec: Number.isFinite(timeline.durationSec) ? timeline.durationSec : 0,
    frameRate: Number.isFinite(timeline.frameRate) ? timeline.frameRate : 30,
    frames: timeline.frames.map((frame) => ({
      ...frame,
      energyBands: Float32Array.from(frame.energyBands ?? []),
      peakHoldBands: Float32Array.from(frame.peakHoldBands ?? []),
      transientBands: Float32Array.from(frame.transientBands ?? []),
      onsetBands: Float32Array.from(frame.onsetBands ?? []),
    })),
  }
}

export function samplePreviewAudioReactiveFeatureTimeline(
  timeline: PreviewAudioReactiveFeatureTimeline | null,
  timeSec: number,
): PreviewAudioReactiveFeatureSample | null {
  if (!timeline?.frames.length) {
    return null
  }

  const clampedTime = clamp(timeSec, 0, Math.max(0, timeline.durationSec))
  const framePosition = clampedTime * timeline.frameRate
  const lowerIndex = clamp(Math.floor(framePosition), 0, timeline.frames.length - 1)
  const upperIndex = clamp(Math.ceil(framePosition), 0, timeline.frames.length - 1)
  const lower = timeline.frames[lowerIndex]
  const upper = timeline.frames[upperIndex]
  if (lowerIndex === upperIndex) {
    return {
      ...lower,
      timeSec: clampedTime,
    }
  }

  const mixAmount = clamp(framePosition - lowerIndex, 0, 1)
  return {
    timeSec: clampedTime,
    energyBands: Float32Array.from({ length: AUDIO_SPECTRUM_BINS }, (_, index) =>
      lerp(lower.energyBands[index] ?? 0, upper.energyBands[index] ?? 0, mixAmount),
    ),
    peakHoldBands: Float32Array.from({ length: AUDIO_SPECTRUM_BINS }, (_, index) =>
      Math.max(lower.peakHoldBands[index] ?? 0, upper.peakHoldBands[index] ?? 0),
    ),
    transientBands: Float32Array.from({ length: AUDIO_SPECTRUM_BINS }, (_, index) =>
      lerp(lower.transientBands[index] ?? 0, upper.transientBands[index] ?? 0, mixAmount),
    ),
    onsetBands: Float32Array.from({ length: AUDIO_SPECTRUM_BINS }, (_, index) =>
      lerp(lower.onsetBands[index] ?? 0, upper.onsetBands[index] ?? 0, mixAmount),
    ),
    framePeak: lerp(lower.framePeak, upper.framePeak, mixAmount),
    averageEnergy: lerp(lower.averageEnergy, upper.averageEnergy, mixAmount),
    averageTransient: lerp(lower.averageTransient, upper.averageTransient, mixAmount),
    averageOnset: lerp(lower.averageOnset, upper.averageOnset, mixAmount),
    level: lerp(lower.level, upper.level, mixAmount),
    kick: lerp(lower.kick, upper.kick, mixAmount),
    drop: lerp(lower.drop, upper.drop, mixAmount),
    reactiveEnergy: lerp(lower.reactiveEnergy, upper.reactiveEnergy, mixAmount),
    bass: lerp(lower.bass, upper.bass, mixAmount),
    mid: lerp(lower.mid, upper.mid, mixAmount),
    treble: lerp(lower.treble, upper.treble, mixAmount),
    energy: lerp(lower.energy, upper.energy, mixAmount),
    onset: lerp(lower.onset, upper.onset, mixAmount),
    transient: lerp(lower.transient, upper.transient, mixAmount),
    beat: Math.max(lower.beat, upper.beat),
  }
}
