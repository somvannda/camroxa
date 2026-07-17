import type { PreviewReactiveFrameDraft } from '@/features/video/core/contracts/previewDraftContracts'
import type { PreviewGpuAudioSignalFrame } from '@/features/video/core/contracts/previewGpuAudioSignalContract'
import {
  analyseAudioSpectrumFrame,
  buildAudioSpectrumFrameFromFeatures,
  type AudioSpectrumFrame,
} from '@/features/video/preview/audioSpectrumAnalysis'
import type { AudioAnalysisRuntime } from '@/features/video/preview/audioFeatureBus'
import { buildPreviewGpuAudioSignalFrame } from '@/features/video/preview/previewGpuAudioSignal'
import {
  samplePreviewAudioReactiveFeatureTimeline,
} from '@/features/video/preview/audioReactiveTimeline'
import { resolveLogoReactiveDriveEnergy } from '@/features/video/domains/logo/logoPreviewRuntime'
import { normalizeSpectrumStyleKey } from '@/features/video/domains/spectrum/spectrumLayerModel'

export type PreviewReactiveMotionState = {
  backgroundEnergy: number
  backgroundBeatBaseline: number
  backgroundPulseDrive: number
  logoEnergy: number
  logoBeatBaseline: number
  logoPulseDrive: number
  flyingGlowLastTriggerDrive: number
  flyingGlowPulseDrive: number
  flyingGlowLastTriggerSec: number
  flyingGlowBeatIntervalSec: number
}

function applySpectrumFrameInputGain(
  frame: AudioSpectrumFrame,
  inputGain: number,
): AudioSpectrumFrame {
  const safeInputGain = clamp(inputGain, 0.25, 10)
  if (Math.abs(safeInputGain - 1) <= 0.0001) {
    return frame
  }

  const renderGain = safeInputGain >= 1 ? 1 + (safeInputGain - 1) * 0.26 : safeInputGain
  const renderValues = Float32Array.from(frame.renderValues, (value) =>
    clamp(value * renderGain, 0, 1),
  )
  const peakHoldValues = frame.peakHoldValues
    ? Float32Array.from(frame.peakHoldValues, (value) => clamp(value * renderGain, 0, 1))
    : undefined
  const averageEnergy = renderValues.length
    ? renderValues.reduce((sum, value) => sum + value, 0) / renderValues.length
    : frame.reactiveEnergy

  return {
    ...frame,
    renderValues,
    peakHoldValues,
    reactiveEnergy: clamp(
      Math.max(frame.reactiveEnergy, averageEnergy + Math.max(0, safeInputGain - 1) * 0.035),
      0,
      1,
    ),
  }
}

type ResolvePreviewReactiveFrameStateOptions = {
  averageValues: (values: ArrayLike<number>, count?: number) => number
  buildLayerSpectrumValues: (count: number, frame: AudioSpectrumFrame | null, mirrored: boolean) => number[] | null
  buildSyntheticSpectrumValues: (
    count: number,
    timeSec: number,
    sensitivity: number,
    smoothing: number,
    layerIndex: number,
  ) => number[]
  deltaSec: number
  forcePlaybackActive?: boolean
  motionState: PreviewReactiveMotionState
  playbackTimeSecOverride?: number
  runtime: AudioAnalysisRuntime
  selectedMp3Path: string
  smoothPreviewReactiveValue: (
    current: number,
    target: number,
    deltaSec: number,
    smoothing: number,
  ) => number
  spectrumBarCount: number
  reactiveDraft: PreviewReactiveFrameDraft
  timeSec: number
  updateFlyingGlowWingEnvelope: (
    currentPulse: number,
    supportDrive: number,
    triggerDrive: number,
    lastTriggerDrive: number,
    timeSec: number,
    deltaSec: number,
    lastTriggerSec: number,
    beatIntervalSec: number,
      motionSpeed: number,
    releaseControl: number,
  ) => {
    pulseDrive: number
    lastTriggerDrive: number
    lastTriggerSec: number
    beatIntervalSec: number
  }
}

type ResolvePreviewReactiveFrameStateResult = {
  analysedFrame: AudioSpectrumFrame | null
  audioSignal: PreviewGpuAudioSignalFrame | null
  hasBoundAudio: boolean
  playbackActive: boolean
  reactiveEnergy: number
  spectrumValues: number[]
  timing: {
    audioMs: number
    spectrumMs: number
  }
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value))
}

function resolveSharedReactiveSupportDrive(
  audioSignal: PreviewGpuAudioSignalFrame | null,
  reactiveEnergy: number,
): number {
  return clamp(
    Math.max(
      reactiveEnergy,
      audioSignal?.reactiveEnergy ?? 0,
      audioSignal?.styleMotionDrive ?? 0,
      audioSignal?.averageEnergy ?? 0,
    ),
    0,
    1,
  )
}

function resolveSharedReactiveTriggerDrive(
  audioSignal: PreviewGpuAudioSignalFrame | null,
  supportDrive: number,
): number {
  return clamp(
    Math.max(
      audioSignal?.styleTriggerDrive ?? 0,
      audioSignal?.averageTransient ?? 0,
      audioSignal?.averageOnset ?? 0,
      audioSignal?.kick ?? 0,
      audioSignal?.drop ?? 0,
      supportDrive * 0.72,
    ),
    0,
    1,
  )
}

export function resolvePreviewReactiveFrameState({
  averageValues,
  buildLayerSpectrumValues,
  buildSyntheticSpectrumValues,
  deltaSec,
  forcePlaybackActive = false,
  motionState,
  playbackTimeSecOverride,
  runtime,
  selectedMp3Path,
  smoothPreviewReactiveValue,
  spectrumBarCount,
  reactiveDraft,
  timeSec,
  updateFlyingGlowWingEnvelope,
}: ResolvePreviewReactiveFrameStateOptions): ResolvePreviewReactiveFrameStateResult {
  let analysedFrame: AudioSpectrumFrame | null = null
  let audioMs = 0
  const timelineTimeSec =
    (typeof playbackTimeSecOverride === 'number' && Number.isFinite(playbackTimeSecOverride)
      ? playbackTimeSecOverride
      : undefined) ??
    runtime.audioElement?.currentTime ??
    timeSec
  const sampledFeatures = samplePreviewAudioReactiveFeatureTimeline(
    runtime.featureTimeline,
    timelineTimeSec,
  )

  if (sampledFeatures) {
    const audioStart = performance.now()
    analysedFrame = applySpectrumFrameInputGain(
      buildAudioSpectrumFrameFromFeatures(
        sampledFeatures,
        reactiveDraft.audioBandContrast,
        reactiveDraft.audioTransientFocus,
        reactiveDraft.audioKickImpact,
        reactiveDraft.style ?? '',
        reactiveDraft.audioBarHeight,
        reactiveDraft.audioBassEmphasis,
        reactiveDraft.audioTrebleShimmer,
        reactiveDraft.audioPeakHoldBlend,
      ),
      reactiveDraft.audioInputGain,
    )
    audioMs = performance.now() - audioStart
  } else if (runtime.analyser && runtime.frequencyData) {
    const audioStart = performance.now()
    runtime.analyser.smoothingTimeConstant = clamp(reactiveDraft.audioMotionSmoothing, 0, 0.97)
    runtime.analyser.getByteFrequencyData(runtime.frequencyData)
    analysedFrame = analyseAudioSpectrumFrame(
      runtime.frequencyData,
      reactiveDraft.audioInputGain,
      reactiveDraft.audioBandContrast,
      reactiveDraft.audioTransientFocus,
      reactiveDraft.audioKickImpact,
      deltaSec,
      runtime.spectrumMapping,
      runtime.envelope,
      reactiveDraft.style ?? '',
      reactiveDraft.audioBarHeight,
      reactiveDraft.audioBassEmphasis,
      reactiveDraft.audioTrebleShimmer,
      reactiveDraft.audioPeakHoldBlend,
    )
    audioMs = performance.now() - audioStart
  }

  const hasBoundAudio = Boolean(selectedMp3Path.trim() && runtime.audioElement)
  const playbackActive = forcePlaybackActive
    ? true
    : hasBoundAudio
    ? Boolean(runtime.audioElement && !runtime.audioElement.paused && !runtime.audioElement.ended)
    : true

  const spectrumStart = performance.now()
  const previewAudioSignal = buildPreviewGpuAudioSignalFrame({
    features: sampledFeatures ?? analysedFrame?.sourceFeatures ?? null,
    frame: analysedFrame,
    reactiveEnergy: playbackActive
      ? sampledFeatures?.reactiveEnergy ?? analysedFrame?.reactiveEnergy ?? 0
      : 0,
    spectrumBarCount,
    timeSec: timelineTimeSec,
  })
  const spectrumValues =
    (previewAudioSignal?.mirroredRenderValues?.length ? previewAudioSignal.mirroredRenderValues : null) ??
    buildLayerSpectrumValues(spectrumBarCount, analysedFrame, true) ??
    (hasBoundAudio
      ? Array.from({ length: spectrumBarCount }, () => 0)
      : buildSyntheticSpectrumValues(
          spectrumBarCount,
          timeSec,
          reactiveDraft.audioInputGain,
          reactiveDraft.audioMotionSmoothing,
          0,
        ))
  const averageEnergy = averageValues(spectrumValues)
  const reactiveEnergy = playbackActive
    ? sampledFeatures?.reactiveEnergy ?? analysedFrame?.reactiveEnergy ?? averageEnergy
    : 0
  const audioSignal =
    previewAudioSignal && reactiveEnergy === previewAudioSignal.reactiveEnergy
      ? previewAudioSignal
      : buildPreviewGpuAudioSignalFrame({
          features: sampledFeatures ?? analysedFrame?.sourceFeatures ?? null,
          frame: analysedFrame,
          reactiveEnergy,
          spectrumBarCount,
          timeSec: timelineTimeSec,
        })
  const kickEnergy = sampledFeatures?.kick ?? runtime.envelope.kick
  const dropEnergy = sampledFeatures?.drop ?? runtime.envelope.drop
  const sharedSupportDrive = resolveSharedReactiveSupportDrive(audioSignal, reactiveEnergy)
  const sharedTriggerDrive = resolveSharedReactiveTriggerDrive(audioSignal, sharedSupportDrive)
  // Revamped: much simpler, more responsive background pulse
  const backgroundPulseTarget = clamp(
    Math.max(
      audioSignal?.styleTriggerDrive ?? 0,
      audioSignal?.averageTransient ?? 0,
      audioSignal?.averageOnset ?? 0,
      audioSignal?.kick ?? 0,
      audioSignal?.drop ?? 0,
      sampledFeatures?.beat ?? 0,
      reactiveEnergy * 0.4,
    ),
    0,
    1,
  )
  const backgroundSmoothing = clamp(0.01 + reactiveDraft.backgroundSmoothing * 0.008, 0.01, 0.12)
  const isFlyingGlowStyle = normalizeSpectrumStyleKey(reactiveDraft.style ?? '') === 'flying-glow'

  motionState.backgroundEnergy = smoothPreviewReactiveValue(
    motionState.backgroundEnergy,
    backgroundPulseTarget,
    deltaSec,
    0.06,
  )
  motionState.backgroundBeatBaseline = 0 // No more baseline gating
  motionState.backgroundPulseDrive = smoothPreviewReactiveValue(
    motionState.backgroundPulseDrive,
    backgroundPulseTarget,
    deltaSec,
    backgroundSmoothing,
  )

  motionState.logoEnergy = smoothPreviewReactiveValue(
    motionState.logoEnergy,
    sharedSupportDrive,
    deltaSec,
    reactiveDraft.logoSmoothing,
  )
  motionState.logoBeatBaseline = smoothPreviewReactiveValue(
    motionState.logoBeatBaseline,
    sharedSupportDrive,
    deltaSec,
    clamp(0.9 + reactiveDraft.logoSmoothing * 0.08, 0.9, 0.98),
  )
  const logoBeatDelta = Math.max(0, sharedTriggerDrive - motionState.logoBeatBaseline)
  const logoReactiveDrive = resolveLogoReactiveDriveEnergy(
    motionState.logoEnergy,
    logoBeatDelta,
    kickEnergy,
    dropEnergy,
  )
  motionState.logoPulseDrive = smoothPreviewReactiveValue(
    motionState.logoPulseDrive,
    logoReactiveDrive,
    deltaSec,
    clamp(0.1 + reactiveDraft.logoSmoothing * 0.22, 0.1, 0.42),
  )

  if (playbackActive && isFlyingGlowStyle) {
    const nextFlyingGlowWingEnvelope = updateFlyingGlowWingEnvelope(
      motionState.flyingGlowPulseDrive,
      analysedFrame?.styleMotionDrive ?? 0,
      analysedFrame?.styleTriggerDrive ?? analysedFrame?.styleMotionDrive ?? 0,
      motionState.flyingGlowLastTriggerDrive,
      timeSec,
      deltaSec,
      motionState.flyingGlowLastTriggerSec,
      motionState.flyingGlowBeatIntervalSec,
      reactiveDraft.flyingGlowWingMotionSpeed,
      reactiveDraft.flyingGlowWingRelease,
    )
    motionState.flyingGlowPulseDrive = nextFlyingGlowWingEnvelope.pulseDrive
    motionState.flyingGlowLastTriggerDrive = nextFlyingGlowWingEnvelope.lastTriggerDrive
    motionState.flyingGlowLastTriggerSec = nextFlyingGlowWingEnvelope.lastTriggerSec
    motionState.flyingGlowBeatIntervalSec = nextFlyingGlowWingEnvelope.beatIntervalSec
  } else {
    motionState.flyingGlowLastTriggerDrive = 0
    motionState.flyingGlowPulseDrive = smoothPreviewReactiveValue(
      motionState.flyingGlowPulseDrive,
      0,
      deltaSec,
      0.04,
    )
    motionState.flyingGlowLastTriggerSec = -1
    motionState.flyingGlowBeatIntervalSec = 0.2
  }

  return {
    analysedFrame,
    audioSignal,
    hasBoundAudio,
    playbackActive,
    reactiveEnergy,
    spectrumValues,
    timing: {
      audioMs,
      spectrumMs: performance.now() - spectrumStart,
    },
  }
}
