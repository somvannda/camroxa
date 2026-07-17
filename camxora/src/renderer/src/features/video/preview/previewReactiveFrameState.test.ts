import {
  resolvePreviewReactiveFrameState,
  type PreviewReactiveMotionState,
} from '@/features/video/preview/previewReactiveFrameState'
import type { PreviewAudioReactiveFeatureTimeline } from '@/features/video/preview/audioReactiveTimeline'

const mockAnalyseAudioSpectrumFrame = vi.fn()
const mockBuildAudioSpectrumFrameFromFeatures = vi.fn()
const mockNormalizeSpectrumStyleKey = vi.fn()
const mockResolveBackgroundReactiveDriveEnergy = vi.fn()
const mockResolveLogoReactiveDriveEnergy = vi.fn()

vi.mock('@/features/video/preview/audioSpectrumAnalysis', () => ({
  AUDIO_SPECTRUM_BINS: 64,
  analyseAudioSpectrumFrame: (...args: unknown[]) => mockAnalyseAudioSpectrumFrame(...args),
  buildAudioSpectrumFrameFromFeatures: (...args: unknown[]) =>
    mockBuildAudioSpectrumFrameFromFeatures(...args),
}))

vi.mock('@/features/video/domains/spectrum/spectrumLayerModel', () => ({
  normalizeSpectrumStyleKey: (...args: unknown[]) => mockNormalizeSpectrumStyleKey(...args),
}))

vi.mock('@/features/video/domains/background/backgroundPreviewRuntime', () => ({
  resolveBackgroundReactiveDriveEnergy: (...args: unknown[]) => mockResolveBackgroundReactiveDriveEnergy(...args),
}))

vi.mock('@/features/video/domains/logo/logoPreviewRuntime', () => ({
  resolveLogoReactiveDriveEnergy: (...args: unknown[]) => mockResolveLogoReactiveDriveEnergy(...args),
}))

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

describe('resolvePreviewReactiveFrameState', () => {
  beforeEach(() => {
    mockAnalyseAudioSpectrumFrame.mockReset()
    mockBuildAudioSpectrumFrameFromFeatures.mockReset()
    mockNormalizeSpectrumStyleKey.mockReset()
    mockResolveBackgroundReactiveDriveEnergy.mockReset()
    mockResolveLogoReactiveDriveEnergy.mockReset()
  })

  it('analyses bound audio and updates reactive motion state', () => {
    const frequencyData = new Uint8Array([8, 16, 32])
    const envelope = { kick: 0.4, drop: 0.2 }
    const analyser = {
      smoothingTimeConstant: 0,
      getByteFrequencyData: vi.fn(),
    }
    const runtime = {
      analyser,
      frequencyData,
      audioContext: null,
      audioElement: { paused: false, ended: false },
      gainNode: null,
      spectrumMapping: null,
      envelope,
    } as never
    const motionState = createMotionState()

    mockAnalyseAudioSpectrumFrame.mockReturnValue({
      reactiveEnergy: 0.65,
      renderValues: new Float32Array([0.2, 0.4, 0.6]),
      peakHoldValues: new Float32Array([0.3, 0.45, 0.7]),
      styleMotionDrive: 0.4,
      styleTriggerDrive: 0.7,
      sourceFeatures: {
        energyBands: new Float32Array(64).fill(0.25),
        peakHoldBands: new Float32Array(64).fill(0.35),
        transientBands: new Float32Array(64).fill(0.12),
        onsetBands: new Float32Array(64).fill(0.18),
        framePeak: 0.8,
        averageEnergy: 0.25,
        averageTransient: 0.12,
        averageOnset: 0.18,
        level: 0.7,
        kick: 0.4,
        drop: 0.2,
      },
    })
    mockNormalizeSpectrumStyleKey.mockReturnValue('flying-glow')
    mockResolveBackgroundReactiveDriveEnergy.mockReturnValue(0.5)
    mockResolveLogoReactiveDriveEnergy.mockReturnValue(0.6)

    const smoothPreviewReactiveValue = vi
      .fn()
      .mockImplementation((_current: number, target: number) => target)
    const updateFlyingGlowWingEnvelope = vi.fn().mockReturnValue({
      pulseDrive: 0.9,
      lastTriggerDrive: 0.7,
      lastTriggerSec: 1.2,
      beatIntervalSec: 0.18,
    })

    const result = resolvePreviewReactiveFrameState({
      averageValues: vi.fn().mockReturnValue(0.2),
      buildLayerSpectrumValues: vi.fn().mockReturnValue([0.2, 0.4, 0.6]),
      buildSyntheticSpectrumValues: vi.fn(),
      deltaSec: 0.016,
      motionState,
      runtime,
      selectedMp3Path: 'D:/song.mp3',
      smoothPreviewReactiveValue,
      spectrumBarCount: 3,
      reactiveDraft: {
        audioBandContrast: 1,
        audioBarHeight: 1.4,
        audioBassEmphasis: 1.7,
        audioInputGain: 1,
        audioKickImpact: 1,
        audioMotionSmoothing: 0.7,
        audioPeakHoldBlend: 0.55,
        audioTrebleShimmer: 1.35,
        audioTransientFocus: 1,
        backgroundSmoothing: 0.5,
        flyingGlowWingRelease: 1.1,
        logoSmoothing: 0.4,
        style: 'flying-glow',
      } as never,
      timeSec: 1.2,
      updateFlyingGlowWingEnvelope,
    })

    expect(analyser.getByteFrequencyData).toHaveBeenCalledWith(frequencyData)
    expect(mockAnalyseAudioSpectrumFrame).toHaveBeenCalledWith(
      frequencyData,
      1,
      1,
      1,
      1,
      0.016,
      null,
      envelope,
      'flying-glow',
      1.4,
      1.7,
      1.35,
      0.55,
    )
    expect(result.hasBoundAudio).toBe(true)
    expect(result.playbackActive).toBe(true)
    expect(result.reactiveEnergy).toBe(0.65)
    expect(result.spectrumValues.map((value) => Number(value.toFixed(3)))).toEqual([0.2, 0.2, 0.4])
    expect(result.audioSignal?.reactiveEnergy).toBe(0.65)
    expect(result.audioSignal?.renderValues.map((value) => Number(value.toFixed(3)))).toEqual([0.2, 0.4, 0.6])
    expect(updateFlyingGlowWingEnvelope).toHaveBeenCalled()
    expect(motionState.backgroundPulseDrive).toBe(0.7)
    expect(motionState.logoPulseDrive).toBe(0.6)
    expect(motionState.flyingGlowPulseDrive).toBe(0.9)
  })

  it('falls back to synthetic values and closes flying glow state when playback is inactive', () => {
    const motionState = createMotionState()
    motionState.flyingGlowPulseDrive = 0.4
    motionState.flyingGlowLastTriggerDrive = 0.6

    mockNormalizeSpectrumStyleKey.mockReturnValue('straight-bars')
    mockResolveBackgroundReactiveDriveEnergy.mockReturnValue(0)
    mockResolveLogoReactiveDriveEnergy.mockReturnValue(0)

    const buildSyntheticSpectrumValues = vi.fn().mockReturnValue([0.1, 0.2])
    const smoothPreviewReactiveValue = vi
      .fn()
      .mockImplementation((_current: number, target: number) => target)

    const result = resolvePreviewReactiveFrameState({
      averageValues: vi.fn().mockReturnValue(0.15),
      buildLayerSpectrumValues: vi.fn().mockReturnValue(null),
      buildSyntheticSpectrumValues,
      deltaSec: 0.02,
      motionState,
      runtime: {
        analyser: null,
        frequencyData: null,
        audioContext: null,
        audioElement: null,
        gainNode: null,
        spectrumMapping: null,
        envelope: { kick: 0, drop: 0 },
      } as never,
      selectedMp3Path: '',
      smoothPreviewReactiveValue,
      spectrumBarCount: 2,
      reactiveDraft: {
        audioBandContrast: 1,
        audioBarHeight: 1,
        audioBassEmphasis: 1,
        audioInputGain: 1,
        audioKickImpact: 1,
        audioMotionSmoothing: 0.7,
        audioPeakHoldBlend: 0,
        audioTrebleShimmer: 1,
        audioTransientFocus: 1,
        backgroundSmoothing: 0.5,
        flyingGlowWingRelease: 1,
        logoSmoothing: 0.4,
        style: 'straight-bars',
      } as never,
      timeSec: 2,
      updateFlyingGlowWingEnvelope: vi.fn(),
    })

    expect(buildSyntheticSpectrumValues).toHaveBeenCalledWith(2, 2, 1, 0.7, 0)
    expect(result.hasBoundAudio).toBe(false)
    expect(result.playbackActive).toBe(true)
    expect(result.reactiveEnergy).toBe(0.15)
    expect(result.audioSignal).toBeNull()
    expect(motionState.flyingGlowLastTriggerDrive).toBe(0)
    expect(motionState.flyingGlowPulseDrive).toBe(0)
    expect(motionState.flyingGlowLastTriggerSec).toBe(-1)
  })

  it('prefers the sampled analyzed timeline for reactive energy and kick/drop inputs when available', () => {
    const frequencyData = new Uint8Array([8, 16, 32])
    const analyser = {
      smoothingTimeConstant: 0,
      getByteFrequencyData: vi.fn(),
    }
    const featureTimeline: PreviewAudioReactiveFeatureTimeline = {
      durationSec: 2,
      frameRate: 10,
      frames: [
        {
          timeSec: 0,
          energyBands: new Float32Array(64),
          peakHoldBands: new Float32Array(64),
          transientBands: new Float32Array(64),
          onsetBands: new Float32Array(64),
          framePeak: 0.2,
          averageEnergy: 0.1,
          averageTransient: 0.1,
          averageOnset: 0.1,
          level: 0.2,
          bass: 0.1,
          mid: 0.1,
          treble: 0.1,
          energy: 0.2,
          onset: 0.1,
          transient: 0.1,
          beat: 0,
          kick: 0.15,
          drop: 0.08,
          reactiveEnergy: 0.2,
        },
        {
          timeSec: 0.1,
          energyBands: new Float32Array(64).fill(0.4),
          peakHoldBands: new Float32Array(64).fill(0.5),
          transientBands: new Float32Array(64).fill(0.2),
          onsetBands: new Float32Array(64).fill(0.3),
          framePeak: 0.9,
          averageEnergy: 0.45,
          averageTransient: 0.2,
          averageOnset: 0.25,
          level: 0.8,
          bass: 0.9,
          mid: 0.3,
          treble: 0.2,
          energy: 0.8,
          onset: 0.6,
          transient: 0.4,
          beat: 1,
          kick: 0.72,
          drop: 0.58,
          reactiveEnergy: 0.84,
        },
      ],
    }
    const runtime = {
      analyser,
      frequencyData,
      audioContext: null,
      audioElement: { paused: false, ended: false, currentTime: 0.1 },
      featureTimeline,
      gainNode: null,
      spectrumMapping: null,
      envelope: { kick: 0.2, drop: 0.1 },
    } as never
    const motionState = createMotionState()

    mockAnalyseAudioSpectrumFrame.mockReturnValue({
      reactiveEnergy: 0.25,
      styleMotionDrive: 0.2,
      styleTriggerDrive: 0.3,
    })
    mockBuildAudioSpectrumFrameFromFeatures.mockReturnValue({
      reactiveEnergy: 0.84,
      renderValues: new Float32Array([0.3, 0.45, 0.6]),
      styleMotionDrive: 0.2,
      styleTriggerDrive: 0.3,
    })
    mockNormalizeSpectrumStyleKey.mockReturnValue('straight-bars')
    mockResolveBackgroundReactiveDriveEnergy.mockReturnValue(0.42)
    mockResolveLogoReactiveDriveEnergy.mockReturnValue(0.51)

    const result = resolvePreviewReactiveFrameState({
      averageValues: vi.fn().mockReturnValue(0.2),
      buildLayerSpectrumValues: vi.fn().mockReturnValue([0.2, 0.4, 0.6]),
      buildSyntheticSpectrumValues: vi.fn(),
      deltaSec: 0.016,
      motionState,
      runtime,
      selectedMp3Path: 'D:/song.mp3',
      smoothPreviewReactiveValue: vi.fn().mockImplementation((_current: number, target: number) => target),
      spectrumBarCount: 3,
      reactiveDraft: {
        audioBandContrast: 1,
        audioBarHeight: 1.3,
        audioBassEmphasis: 1.6,
        audioInputGain: 1,
        audioKickImpact: 1,
        audioMotionSmoothing: 0,
        audioPeakHoldBlend: 0.45,
        audioTrebleShimmer: 1.25,
        audioTransientFocus: 1,
        backgroundSmoothing: 0.5,
        flyingGlowWingRelease: 1,
        logoSmoothing: 0.4,
        style: 'straight-bars',
      } as never,
      timeSec: 1.2,
      updateFlyingGlowWingEnvelope: vi.fn(),
    })

    expect(result.reactiveEnergy).toBeCloseTo(0.84, 5)
    expect(result.audioSignal?.kick).toBeCloseTo(0.72, 5)
    expect(result.audioSignal?.drop).toBeCloseTo(0.58, 5)
    expect(result.audioSignal?.renderValues.map((value) => Number(value.toFixed(3)))).toEqual([0.3, 0.45, 0.6])
    expect(result.audioSignal?.mirroredRenderValues.map((value) => Number(value.toFixed(3)))).toEqual([0.3, 0.3, 0.45])
    expect(analyser.getByteFrequencyData).not.toHaveBeenCalled()
    expect(mockBuildAudioSpectrumFrameFromFeatures).toHaveBeenCalledWith(
      expect.objectContaining({
        reactiveEnergy: 0.84,
        kick: 0.72,
        drop: 0.58,
      }),
      1,
      1,
      1,
      'straight-bars',
      1.3,
      1.6,
      1.25,
      0.45,
    )
    const [logoEnergy, logoBeatDelta, logoKick, logoDrop] =
      mockResolveLogoReactiveDriveEnergy.mock.calls[0]
    expect(motionState.backgroundPulseDrive).toBeCloseTo(1, 5)
    expect(logoEnergy).toBeCloseTo(0.84, 5)
    expect(logoBeatDelta).toBe(0)
    expect(logoKick).toBe(0.72)
    expect(logoDrop).toBe(0.58)
  })

  it('applies input gain to the sampled feature-timeline spectrum output', () => {
    const runtime = {
      analyser: null,
      frequencyData: null,
      audioContext: null,
      audioElement: { paused: false, ended: false, currentTime: 0.1 },
      featureTimeline: {
        durationSec: 1,
        frameRate: 10,
        frames: [
          {
            timeSec: 0.1,
            energyBands: new Float32Array(64).fill(0.2),
            peakHoldBands: new Float32Array(64).fill(0.25),
            transientBands: new Float32Array(64).fill(0.08),
            onsetBands: new Float32Array(64).fill(0.09),
            framePeak: 0.5,
            averageEnergy: 0.2,
            averageTransient: 0.08,
            averageOnset: 0.09,
            level: 0.45,
            bass: 0.2,
            mid: 0.15,
            treble: 0.12,
            energy: 0.3,
            onset: 0.12,
            transient: 0.1,
            beat: 0,
            kick: 0.18,
            drop: 0.14,
            reactiveEnergy: 0.28,
          },
        ],
      } as PreviewAudioReactiveFeatureTimeline,
      gainNode: null,
      spectrumMapping: null,
      envelope: { kick: 0.1, drop: 0.08 },
    } as never
    const motionState = createMotionState()

    mockBuildAudioSpectrumFrameFromFeatures.mockReturnValue({
      reactiveEnergy: 0.28,
      renderValues: new Float32Array([0.1, 0.2, 0.3]),
      peakHoldValues: new Float32Array([0.12, 0.22, 0.32]),
      styleMotionDrive: 0.12,
      styleTriggerDrive: 0.18,
    })
    mockNormalizeSpectrumStyleKey.mockReturnValue('straight-bars')
    mockResolveLogoReactiveDriveEnergy.mockReturnValue(0.2)

    const result = resolvePreviewReactiveFrameState({
      averageValues: vi.fn().mockReturnValue(0.2),
      buildLayerSpectrumValues: vi.fn().mockReturnValue([0.1, 0.2, 0.3]),
      buildSyntheticSpectrumValues: vi.fn(),
      deltaSec: 0.016,
      motionState,
      runtime,
      selectedMp3Path: 'D:/song.mp3',
      smoothPreviewReactiveValue: vi.fn().mockImplementation((_current: number, target: number) => target),
      spectrumBarCount: 3,
      reactiveDraft: {
        audioBandContrast: 1,
        audioBarHeight: 1,
        audioBassEmphasis: 1,
        audioInputGain: 4,
        audioKickImpact: 1,
        audioMotionSmoothing: 0,
        audioPeakHoldBlend: 0,
        audioTrebleShimmer: 1,
        audioTransientFocus: 1,
        backgroundSmoothing: 0.5,
        flyingGlowWingRelease: 1,
        logoSmoothing: 0.4,
        style: 'straight-bars',
      } as never,
      timeSec: 0.1,
      updateFlyingGlowWingEnvelope: vi.fn(),
    })

    expect(result.audioSignal?.renderValues[0] ?? 0).toBeGreaterThan(0.1)
    expect(result.audioSignal?.renderValues[1] ?? 0).toBeGreaterThan(0.2)
    expect(result.audioSignal?.renderValues[2] ?? 0).toBeGreaterThan(0.3)
  })

  it('prefers an explicit playback-time override when sampling the reactive timeline', () => {
    const runtime = {
      analyser: null,
      frequencyData: null,
      audioContext: null,
      audioElement: { paused: false, ended: false, currentTime: 0.1 },
      featureTimeline: {
        durationSec: 1,
        frameRate: 10,
        frames: [
          {
            timeSec: 0.1,
            energyBands: new Float32Array(64).fill(0.1),
            peakHoldBands: new Float32Array(64).fill(0.12),
            transientBands: new Float32Array(64).fill(0.04),
            onsetBands: new Float32Array(64).fill(0.05),
            framePeak: 0.25,
            averageEnergy: 0.1,
            averageTransient: 0.04,
            averageOnset: 0.05,
            level: 0.22,
            bass: 0.12,
            mid: 0.1,
            treble: 0.08,
            energy: 0.2,
            onset: 0.08,
            transient: 0.06,
            beat: 0,
            kick: 0.14,
            drop: 0.11,
            reactiveEnergy: 0.2,
          },
          {
            timeSec: 0.7,
            energyBands: new Float32Array(64).fill(0.5),
            peakHoldBands: new Float32Array(64).fill(0.6),
            transientBands: new Float32Array(64).fill(0.22),
            onsetBands: new Float32Array(64).fill(0.25),
            framePeak: 0.92,
            averageEnergy: 0.5,
            averageTransient: 0.22,
            averageOnset: 0.25,
            level: 0.88,
            bass: 0.74,
            mid: 0.34,
            treble: 0.26,
            energy: 0.84,
            onset: 0.58,
            transient: 0.44,
            beat: 1,
            kick: 0.76,
            drop: 0.62,
            reactiveEnergy: 0.91,
          },
        ],
      } as PreviewAudioReactiveFeatureTimeline,
      gainNode: null,
      spectrumMapping: null,
      envelope: { kick: 0.1, drop: 0.08 },
    } as never
    const motionState = createMotionState()

    mockBuildAudioSpectrumFrameFromFeatures.mockReturnValue({
      reactiveEnergy: 0.91,
      renderValues: new Float32Array([0.4, 0.5, 0.6]),
      peakHoldValues: new Float32Array([0.45, 0.55, 0.65]),
      styleMotionDrive: 0.2,
      styleTriggerDrive: 0.3,
    })
    mockNormalizeSpectrumStyleKey.mockReturnValue('straight-bars')
    mockResolveLogoReactiveDriveEnergy.mockReturnValue(0.3)

    const result = resolvePreviewReactiveFrameState({
      averageValues: vi.fn().mockReturnValue(0.2),
      buildLayerSpectrumValues: vi.fn().mockReturnValue([0.4, 0.5, 0.6]),
      buildSyntheticSpectrumValues: vi.fn(),
      deltaSec: 0.016,
      motionState,
      playbackTimeSecOverride: 0.7,
      runtime,
      selectedMp3Path: 'D:/song.mp3',
      smoothPreviewReactiveValue: vi.fn().mockImplementation((_current: number, target: number) => target),
      spectrumBarCount: 3,
      reactiveDraft: {
        audioBandContrast: 1,
        audioBarHeight: 1,
        audioBassEmphasis: 1,
        audioInputGain: 1,
        audioKickImpact: 1,
        audioMotionSmoothing: 0,
        audioPeakHoldBlend: 0,
        audioTrebleShimmer: 1,
        audioTransientFocus: 1,
        backgroundSmoothing: 0.5,
        flyingGlowWingRelease: 1,
        logoSmoothing: 0.4,
        style: 'straight-bars',
      } as never,
      timeSec: 0.1,
      updateFlyingGlowWingEnvelope: vi.fn(),
    })

    expect(result.reactiveEnergy).toBeCloseTo(0.91, 5)
    expect(result.audioSignal?.timeSec).toBeCloseTo(0.7, 5)
    expect(result.audioSignal?.kick).toBeCloseTo(0.76, 5)
    expect(mockBuildAudioSpectrumFrameFromFeatures).toHaveBeenCalledWith(
      expect.objectContaining({
        reactiveEnergy: 0.91,
        kick: 0.76,
        drop: 0.62,
      }),
      1,
      1,
      1,
      'straight-bars',
      1,
      1,
      1,
      0,
    )
  })
})
