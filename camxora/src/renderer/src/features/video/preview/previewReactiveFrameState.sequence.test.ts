import type { PreviewAudioReactiveFeatureTimeline } from '@/features/video/preview/audioReactiveTimeline'
import { resolvePreviewReactiveFrameState, type PreviewReactiveMotionState } from '@/features/video/preview/previewReactiveFrameState'
import { smoothPreviewReactiveValue, updateFlyingGlowWingEnvelope } from '@/features/video/domains/spectrum/spectrumPreviewRuntime'

function createMotionState(): PreviewReactiveMotionState {
  return {
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
  }
}

function createFeatureFrame(
  timeSec: number,
  values: {
    bass: number
    mid: number
    treble: number
    kick: number
    drop: number
    reactiveEnergy: number
    averageEnergy?: number
    averageTransient?: number
    averageOnset?: number
    beat?: number
    energy?: number
    onset?: number
    transient?: number
  },
) {
  return {
    timeSec,
    energyBands: new Float32Array(64).fill(values.averageEnergy ?? values.reactiveEnergy * 0.5),
    peakHoldBands: new Float32Array(64).fill(values.averageEnergy ?? values.reactiveEnergy * 0.55),
    transientBands: new Float32Array(64).fill(values.averageTransient ?? values.kick * 0.12),
    onsetBands: new Float32Array(64).fill(values.averageOnset ?? values.drop * 0.14),
    framePeak: values.reactiveEnergy,
    averageEnergy: values.averageEnergy ?? values.reactiveEnergy * 0.5,
    averageTransient: values.averageTransient ?? values.kick * 0.12,
    averageOnset: values.averageOnset ?? values.drop * 0.14,
    level: values.reactiveEnergy,
    bass: values.bass,
    mid: values.mid,
    treble: values.treble,
    energy: values.energy ?? values.reactiveEnergy,
    onset: values.onset ?? values.drop * 0.2,
    transient: values.transient ?? values.kick * 0.16,
    beat: values.beat ?? (values.kick >= 0.6 ? 1 : 0),
    kick: values.kick,
    drop: values.drop,
    reactiveEnergy: values.reactiveEnergy,
  }
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

describe('previewReactiveFrameState sequence behavior', () => {
  it('drives background and logo from the shared reactive signal while preserving domain shaping', () => {
    const timeline: PreviewAudioReactiveFeatureTimeline = {
      durationSec: 0.5,
      frameRate: 10,
      frames: [
        createFeatureFrame(0, { bass: 0.05, mid: 0.08, treble: 0.08, kick: 0.02, drop: 0.01, reactiveEnergy: 0.08 }),
        createFeatureFrame(0.1, { bass: 0.34, mid: 0.12, treble: 0.1, kick: 0.04, drop: 0.02, reactiveEnergy: 0.28 }),
        createFeatureFrame(0.2, { bass: 0.22, mid: 0.1, treble: 0.1, kick: 0.82, drop: 0.48, reactiveEnergy: 0.82 }),
        createFeatureFrame(0.3, { bass: 0.28, mid: 0.11, treble: 0.1, kick: 0.18, drop: 0.12, reactiveEnergy: 0.38 }),
        createFeatureFrame(0.4, { bass: 0.2, mid: 0.11, treble: 0.1, kick: 0.76, drop: 0.42, reactiveEnergy: 0.78 }),
      ],
    }
    const motionState = createMotionState()
    const runtime: any = {
      analyser: null,
      frequencyData: null,
      audioContext: null,
      audioElement: { paused: false, ended: false, currentTime: 0 },
      featureTimeline: timeline,
      gainNode: null,
      spectrumMapping: null,
      envelope: { bassFast: 0, bassSlow: 0, kick: 0, drop: 0 },
    }
    const backgroundTrace: number[] = []
    const logoTrace: number[] = []
    const backgroundEnergyTrace: number[] = []
    const logoEnergyTrace: number[] = []

    for (const frame of timeline.frames) {
      runtime.audioElement.currentTime = frame.timeSec
      resolvePreviewReactiveFrameState({
        averageValues,
        buildLayerSpectrumValues: (_count, analysedFrame) => Array.from(analysedFrame?.renderValues ?? []),
        buildSyntheticSpectrumValues: vi.fn(),
        deltaSec: 0.1,
        motionState,
        runtime,
        selectedMp3Path: 'D:/song.mp3',
        smoothPreviewReactiveValue,
        spectrumBarCount: 64,
        reactiveDraft: {
          audioBandContrast: 1,
          audioInputGain: 1,
          audioKickImpact: 1,
          audioMotionSmoothing: 0.7,
          audioTransientFocus: 1,
          backgroundSmoothing: 0.45,
          flyingGlowWingRelease: 1,
          logoSmoothing: 0.35,
          style: 'straight-bars',
        } as never,
        timeSec: frame.timeSec,
        updateFlyingGlowWingEnvelope,
      })
      backgroundTrace.push(motionState.backgroundPulseDrive)
      logoTrace.push(motionState.logoPulseDrive)
      backgroundEnergyTrace.push(motionState.backgroundEnergy)
      logoEnergyTrace.push(motionState.logoEnergy)
    }

    expect(backgroundTrace[2]).toBeGreaterThan(backgroundTrace[1])
    expect(backgroundTrace[2]).toBeGreaterThan(backgroundTrace[0])
    expect(backgroundTrace[3]).toBeLessThan(backgroundTrace[2])
    expect(backgroundTrace[4]).toBeGreaterThan(backgroundTrace[3])

    expect(logoTrace[2]).toBeGreaterThan(backgroundTrace[2])
    expect(logoTrace[4]).toBeGreaterThan(backgroundTrace[4])
    expect(logoTrace[3]).toBeLessThan(logoTrace[2])

    expect(backgroundEnergyTrace[1]).toBeGreaterThan(0.03)
    expect(logoEnergyTrace[1]).toBeGreaterThan(0.15)
    expect(backgroundEnergyTrace[2]).toBeGreaterThan(backgroundEnergyTrace[1])
    expect(logoEnergyTrace[2]).toBeGreaterThan(logoEnergyTrace[1])
    expect(logoEnergyTrace[2]).toBeGreaterThan(0.6)
  })

  it('lets background pulse fall back even when sustained bass support stays present', () => {
    const timeline: PreviewAudioReactiveFeatureTimeline = {
      durationSec: 0.4,
      frameRate: 10,
      frames: [
        createFeatureFrame(0, {
          bass: 0.9,
          mid: 0.14,
          treble: 0.1,
          kick: 0.86,
          drop: 0.52,
          reactiveEnergy: 0.88,
          averageEnergy: 0.82,
          averageTransient: 0.74,
          averageOnset: 0.58,
        }),
        createFeatureFrame(0.1, {
          bass: 0.92,
          mid: 0.14,
          treble: 0.1,
          kick: 0.08,
          drop: 0.06,
          reactiveEnergy: 0.72,
          averageEnergy: 0.78,
          averageTransient: 0.05,
          averageOnset: 0.04,
        }),
        createFeatureFrame(0.2, {
          bass: 0.9,
          mid: 0.14,
          treble: 0.1,
          kick: 0.06,
          drop: 0.04,
          reactiveEnergy: 0.68,
          averageEnergy: 0.75,
          averageTransient: 0.03,
          averageOnset: 0.03,
        }),
      ],
    }
    const motionState = createMotionState()
    const runtime: any = {
      analyser: null,
      frequencyData: null,
      audioContext: null,
      audioElement: { paused: false, ended: false, currentTime: 0 },
      featureTimeline: timeline,
      gainNode: null,
      spectrumMapping: null,
      envelope: { bassFast: 0, bassSlow: 0, kick: 0, drop: 0 },
    }
    const backgroundTrace: number[] = []

    for (const frame of timeline.frames) {
      runtime.audioElement.currentTime = frame.timeSec
      resolvePreviewReactiveFrameState({
        averageValues,
        buildLayerSpectrumValues: (_count, analysedFrame) => Array.from(analysedFrame?.renderValues ?? []),
        buildSyntheticSpectrumValues: vi.fn(),
        deltaSec: 0.1,
        motionState,
        runtime,
        selectedMp3Path: 'D:/song.mp3',
        smoothPreviewReactiveValue,
        spectrumBarCount: 64,
        reactiveDraft: {
          audioBandContrast: 1,
          audioInputGain: 1,
          audioKickImpact: 1,
          audioMotionSmoothing: 0.7,
          audioTransientFocus: 1,
          backgroundSmoothing: 0.45,
          flyingGlowWingRelease: 1,
          logoSmoothing: 0.35,
          style: 'straight-bars',
        } as never,
        timeSec: frame.timeSec,
        updateFlyingGlowWingEnvelope,
      })
      backgroundTrace.push(motionState.backgroundPulseDrive)
    }

    expect(backgroundTrace[0]).toBeGreaterThan(0.7)
    expect(backgroundTrace[1]).toBeLessThan(backgroundTrace[0] * 0.6)
    expect(backgroundTrace[2]).toBeLessThan(backgroundTrace[1])
  })

  it('keeps background moving on the overall rhythmic bed even without a dominant kick spike', () => {
    const timeline: PreviewAudioReactiveFeatureTimeline = {
      durationSec: 0.4,
      frameRate: 10,
      frames: [
        createFeatureFrame(0, {
          bass: 0.28,
          mid: 0.16,
          treble: 0.12,
          kick: 0.08,
          drop: 0.04,
          reactiveEnergy: 0.22,
          averageEnergy: 0.24,
          averageTransient: 0.08,
          averageOnset: 0.09,
          energy: 0.34,
          onset: 0.16,
          transient: 0.14,
          beat: 1,
        }),
        createFeatureFrame(0.1, {
          bass: 0.24,
          mid: 0.15,
          treble: 0.12,
          kick: 0.07,
          drop: 0.04,
          reactiveEnergy: 0.2,
          averageEnergy: 0.22,
          averageTransient: 0.07,
          averageOnset: 0.08,
          energy: 0.3,
          onset: 0.14,
          transient: 0.12,
          beat: 0,
        }),
      ],
    }
    const motionState = createMotionState()
    const runtime: any = {
      analyser: null,
      frequencyData: null,
      audioContext: null,
      audioElement: { paused: false, ended: false, currentTime: 0 },
      featureTimeline: timeline,
      gainNode: null,
      spectrumMapping: null,
      envelope: { bassFast: 0, bassSlow: 0, kick: 0, drop: 0 },
    }
    const backgroundTrace: number[] = []

    for (const frame of timeline.frames) {
      runtime.audioElement.currentTime = frame.timeSec
      resolvePreviewReactiveFrameState({
        averageValues,
        buildLayerSpectrumValues: (_count, analysedFrame) => Array.from(analysedFrame?.renderValues ?? []),
        buildSyntheticSpectrumValues: vi.fn(),
        deltaSec: 0.1,
        motionState,
        runtime,
        selectedMp3Path: 'D:/song.mp3',
        smoothPreviewReactiveValue,
        spectrumBarCount: 64,
        reactiveDraft: {
          audioBandContrast: 1,
          audioInputGain: 1,
          audioKickImpact: 1,
          audioMotionSmoothing: 0.7,
          audioTransientFocus: 1,
          backgroundSmoothing: 0.3,
          flyingGlowWingRelease: 1,
          logoSmoothing: 0.35,
          style: 'straight-bars',
        } as never,
        timeSec: frame.timeSec,
        updateFlyingGlowWingEnvelope,
      })
      backgroundTrace.push(motionState.backgroundPulseDrive)
    }

    expect(backgroundTrace[0]).toBeGreaterThan(0.18)
    expect(backgroundTrace[1]).toBeGreaterThan(0.08)
  })
})
