import {
  buildPreviewAudioReactiveFeatureTimeline,
  deserializePreviewAudioReactiveFeatureTimeline,
  samplePreviewAudioReactiveFeatureTimeline,
  serializePreviewAudioReactiveFeatureTimeline,
  type PreviewAudioReactiveFeatureTimeline,
} from '@/features/video/preview/audioReactiveTimeline'

function createEmptySignal(sampleRate: number, durationSec: number): Float32Array {
  return new Float32Array(Math.round(sampleRate * durationSec))
}

function addToneSegment(
  signal: Float32Array,
  sampleRate: number,
  startSec: number,
  endSec: number,
  frequencyHz: number,
  amplitude: number,
): void {
  const startIndex = Math.max(0, Math.floor(startSec * sampleRate))
  const endIndex = Math.min(signal.length, Math.ceil(endSec * sampleRate))
  const durationSamples = Math.max(1, endIndex - startIndex)

  for (let index = startIndex; index < endIndex; index += 1) {
    const localProgress = (index - startIndex) / durationSamples
    const envelope = Math.sin(localProgress * Math.PI)
    const timeSec = index / sampleRate
    signal[index] += Math.sin(timeSec * Math.PI * 2 * frequencyHz) * amplitude * envelope
  }
}

function createPulseSignal(sampleRate: number, durationSec: number): Float32Array {
  const length = Math.round(sampleRate * durationSec)
  const signal = new Float32Array(length)

  for (let index = 0; index < length; index += 1) {
    const timeSec = index / sampleRate
    const bed = Math.sin(timeSec * Math.PI * 2 * 110) * 0.08
    const pulse =
      (timeSec >= 0.45 && timeSec <= 0.5) || (timeSec >= 0.95 && timeSec <= 1)
        ? Math.sin(timeSec * Math.PI * 2 * 58) * 0.95
        : 0
    signal[index] = bed + pulse
  }

  return signal
}

function createKickHeavySignal(sampleRate: number, durationSec: number): Float32Array {
  const signal = createEmptySignal(sampleRate, durationSec)

  for (let index = 0; index < signal.length; index += 1) {
    const timeSec = index / sampleRate
    signal[index] += Math.sin(timeSec * Math.PI * 2 * 82) * 0.12
    signal[index] += Math.sin(timeSec * Math.PI * 2 * 210) * 0.03
  }

  addToneSegment(signal, sampleRate, 0.22, 0.3, 54, 1.05)
  addToneSegment(signal, sampleRate, 0.7, 0.79, 58, 1.15)
  addToneSegment(signal, sampleRate, 1.18, 1.27, 52, 1.08)
  addToneSegment(signal, sampleRate, 1.66, 1.75, 56, 1.12)
  return signal
}

function createSustainedBassSignal(sampleRate: number, durationSec: number): Float32Array {
  const signal = createEmptySignal(sampleRate, durationSec)

  for (let index = 0; index < signal.length; index += 1) {
    const timeSec = index / sampleRate
    const slowEnvelope = 0.62 + Math.sin(timeSec * Math.PI * 2 * 0.55) * 0.14
    signal[index] += Math.sin(timeSec * Math.PI * 2 * 72) * slowEnvelope * 0.9
    signal[index] += Math.sin(timeSec * Math.PI * 2 * 144) * slowEnvelope * 0.18
    signal[index] += Math.sin(timeSec * Math.PI * 2 * 820) * 0.02
  }

  return signal
}

function createVocalMidSignal(sampleRate: number, durationSec: number): Float32Array {
  const signal = createEmptySignal(sampleRate, durationSec)

  for (let index = 0; index < signal.length; index += 1) {
    const timeSec = index / sampleRate
    signal[index] += Math.sin(timeSec * Math.PI * 2 * 140) * 0.05
  }

  addToneSegment(signal, sampleRate, 0.18, 0.42, 740, 0.82)
  addToneSegment(signal, sampleRate, 0.6, 0.88, 920, 0.92)
  addToneSegment(signal, sampleRate, 1.12, 1.4, 680, 0.88)
  addToneSegment(signal, sampleRate, 1.56, 1.82, 860, 0.86)
  return signal
}

function createTreblePercussionSignal(sampleRate: number, durationSec: number): Float32Array {
  const signal = createEmptySignal(sampleRate, durationSec)

  for (let index = 0; index < signal.length; index += 1) {
    const timeSec = index / sampleRate
    signal[index] += Math.sin(timeSec * Math.PI * 2 * 120) * 0.03
  }

  addToneSegment(signal, sampleRate, 0.24, 0.28, 4_800, 1.05)
  addToneSegment(signal, sampleRate, 0.58, 0.62, 5_400, 1.1)
  addToneSegment(signal, sampleRate, 0.92, 0.96, 6_200, 1.08)
  addToneSegment(signal, sampleRate, 1.28, 1.32, 5_000, 1.06)
  addToneSegment(signal, sampleRate, 1.64, 1.68, 5_800, 1.12)
  return signal
}

function maxFrameValue(
  timeline: PreviewAudioReactiveFeatureTimeline,
  selector: (frame: PreviewAudioReactiveFeatureTimeline['frames'][number]) => number,
): number {
  return Math.max(...timeline.frames.map(selector))
}

function averageBandRange(
  values: ArrayLike<number>,
  startIndex: number,
  endIndex: number,
): number {
  let total = 0
  let count = 0
  for (let index = startIndex; index < endIndex; index += 1) {
    total += values[index] ?? 0
    count += 1
  }
  return count ? total / count : 0
}

describe('audioReactiveTimeline', () => {
  it('builds a deterministic reactivity timeline with kick, onset, and peak-hold around bass pulses', () => {
    const sampleRate = 2_000
    const durationSec = 1.5
    const signal = createPulseSignal(sampleRate, durationSec)

    const timeline = buildPreviewAudioReactiveFeatureTimeline({
      channelData: [signal],
      sampleRate,
      durationSec,
      frameRate: 40,
    })

    const calm = samplePreviewAudioReactiveFeatureTimeline(timeline, 0.2)
    const pulse = samplePreviewAudioReactiveFeatureTimeline(timeline, 0.48)
    const decay = samplePreviewAudioReactiveFeatureTimeline(timeline, 0.62)
    const maxKick = Math.max(...timeline.frames.map((frame) => frame.kick))
    const maxOnset = Math.max(...timeline.frames.map((frame) => frame.onset))

    expect(calm).not.toBeNull()
    expect(pulse).not.toBeNull()
    expect(decay).not.toBeNull()
    expect(maxKick).toBeGreaterThan(0.01)
    expect(maxOnset).toBeGreaterThan(0.001)
    expect((pulse?.averageEnergy ?? 0) > 0 || (decay?.averageEnergy ?? 0) > 0).toBe(true)
    expect(decay?.peakHoldBands[0] ?? 0).toBeGreaterThan(0)
    expect((pulse?.energyBands.length ?? 0) > 0).toBe(true)
  })

  it('interpolates sampled timeline values between analysis frames', () => {
    const timeline: PreviewAudioReactiveFeatureTimeline = {
      durationSec: 1,
      frameRate: 10,
      frames: [
        {
          timeSec: 0,
          energyBands: new Float32Array(64),
          peakHoldBands: new Float32Array(64),
          transientBands: new Float32Array(64),
          onsetBands: new Float32Array(64),
          framePeak: 0,
          averageEnergy: 0,
          averageTransient: 0,
          averageOnset: 0,
          level: 0,
          kick: 0,
          drop: 0,
          reactiveEnergy: 0,
          bass: 0,
          mid: 0,
          treble: 0,
          energy: 0,
          onset: 0,
          transient: 0,
          beat: 0,
        },
        {
          timeSec: 0.1,
          energyBands: new Float32Array(64).fill(0.8),
          peakHoldBands: new Float32Array(64).fill(1),
          transientBands: new Float32Array(64).fill(0.3),
          onsetBands: new Float32Array(64).fill(0.5),
          framePeak: 0.7,
          averageEnergy: 0.8,
          averageTransient: 0.3,
          averageOnset: 0.5,
          level: 0.8,
          kick: 0.7,
          drop: 0.6,
          reactiveEnergy: 0.9,
          bass: 1,
          mid: 0.4,
          treble: 0.2,
          energy: 0.8,
          onset: 0.5,
          transient: 0.3,
          beat: 1,
        },
      ],
    }

    const sample = samplePreviewAudioReactiveFeatureTimeline(timeline, 0.05)

    expect(sample).not.toBeNull()
    expect(sample?.bass).toBeCloseTo(0.5, 5)
    expect(sample?.energy).toBeCloseTo(0.4, 5)
    expect(sample?.kick).toBeCloseTo(0.35, 5)
    expect(sample?.reactiveEnergy).toBeCloseTo(0.45, 5)
    expect(sample?.beat).toBe(1)
    expect(sample?.peakHoldBands[0]).toBe(1)
    expect(sample?.energyBands[0]).toBeCloseTo(0.4, 5)
  })

  it('distinguishes kick-heavy, sustained-bass, vocal-mid, and treble-percussion fixtures with deterministic feature emphasis', () => {
    const sampleRate = 16_000
    const durationSec = 2
    const frameRate = 40

    const kickHeavyTimeline = buildPreviewAudioReactiveFeatureTimeline({
      channelData: [createKickHeavySignal(sampleRate, durationSec)],
      sampleRate,
      durationSec,
      frameRate,
    })
    const sustainedBassTimeline = buildPreviewAudioReactiveFeatureTimeline({
      channelData: [createSustainedBassSignal(sampleRate, durationSec)],
      sampleRate,
      durationSec,
      frameRate,
    })
    const vocalMidTimeline = buildPreviewAudioReactiveFeatureTimeline({
      channelData: [createVocalMidSignal(sampleRate, durationSec)],
      sampleRate,
      durationSec,
      frameRate,
    })
    const trebleTimeline = buildPreviewAudioReactiveFeatureTimeline({
      channelData: [createTreblePercussionSignal(sampleRate, durationSec)],
      sampleRate,
      durationSec,
      frameRate,
    })

    const kickSample = samplePreviewAudioReactiveFeatureTimeline(kickHeavyTimeline, 0.74)
    const bassSample = samplePreviewAudioReactiveFeatureTimeline(sustainedBassTimeline, 0.8)
    const vocalSample = samplePreviewAudioReactiveFeatureTimeline(vocalMidTimeline, 0.72)
    const trebleSample = samplePreviewAudioReactiveFeatureTimeline(trebleTimeline, 0.94)

    expect(kickSample).not.toBeNull()
    expect(bassSample).not.toBeNull()
    expect(vocalSample).not.toBeNull()
    expect(trebleSample).not.toBeNull()

    expect(
      averageBandRange(kickSample?.energyBands ?? [], 0, 8) -
        averageBandRange(kickSample?.energyBands ?? [], 16, 28),
    ).toBeGreaterThan(0.005)
    expect(maxFrameValue(kickHeavyTimeline, (frame) => frame.kick)).toBeGreaterThan(
      maxFrameValue(sustainedBassTimeline, (frame) => frame.kick) + 0.08,
    )
    expect(kickHeavyTimeline.frames.filter((frame) => frame.beat > 0.5).length).toBeGreaterThanOrEqual(3)

    expect(maxFrameValue(sustainedBassTimeline, (frame) => frame.averageEnergy)).toBeGreaterThan(0.02)
    expect(maxFrameValue(sustainedBassTimeline, (frame) => frame.kick)).toBeLessThan(
      maxFrameValue(kickHeavyTimeline, (frame) => frame.kick),
    )
    expect(maxFrameValue(sustainedBassTimeline, (frame) => frame.averageEnergy)).toBeGreaterThan(
      maxFrameValue(sustainedBassTimeline, (frame) => frame.averageTransient),
    )
    expect(sustainedBassTimeline.frames.filter((frame) => frame.beat > 0.5).length).toBeLessThan(
      kickHeavyTimeline.frames.filter((frame) => frame.beat > 0.5).length,
    )

    expect(
      averageBandRange(vocalSample?.energyBands ?? [], 18, 34) -
        Math.max(
          averageBandRange(vocalSample?.energyBands ?? [], 0, 8),
          averageBandRange(vocalSample?.energyBands ?? [], 48, 64),
        ),
    ).toBeGreaterThan(0.015)
    expect(maxFrameValue(vocalMidTimeline, (frame) => frame.onset)).toBeGreaterThan(0.02)

    expect(maxFrameValue(trebleTimeline, (frame) => frame.transient)).toBeGreaterThan(0.05)
    expect(maxFrameValue(trebleTimeline, (frame) => frame.averageTransient)).toBeGreaterThan(0.02)
    expect(maxFrameValue(trebleTimeline, (frame) => frame.averageOnset)).toBeGreaterThan(0.01)
  })

  it('round-trips serialized timelines for persistent preview analysis caching', () => {
    const sampleRate = 4_000
    const durationSec = 1.1
    const frameRate = 30
    const timeline = buildPreviewAudioReactiveFeatureTimeline({
      channelData: [createPulseSignal(sampleRate, durationSec)],
      sampleRate,
      durationSec,
      frameRate,
    })

    const serialized = serializePreviewAudioReactiveFeatureTimeline(timeline)
    const restored = deserializePreviewAudioReactiveFeatureTimeline(serialized)

    expect(restored).not.toBeNull()
    expect(restored?.durationSec).toBeCloseTo(timeline.durationSec, 5)
    expect(restored?.frameRate).toBe(timeline.frameRate)
    expect(restored?.frames).toHaveLength(timeline.frames.length)
    expect(Array.from(restored?.frames[4]?.energyBands ?? [])).toEqual(
      Array.from(timeline.frames[4]?.energyBands ?? []),
    )
    expect(restored?.frames[6]?.kick).toBeCloseTo(timeline.frames[6]?.kick ?? 0, 5)
  })
})
