import { useCallback, useEffect, useRef } from 'react'
import type { MutableRefObject } from 'react'

import {
  applyPreviewAudioMotionSmoothing,
  applyPreviewAudioVolume,
  applyPreviewPlaybackCommand,
  createEmptyAudioAnalysisRuntime,
  createPreviewAudioFeatureBus,
  disposePreviewAudioRuntime,
  type AudioAnalysisRuntime,
} from '@/features/video/preview/audioFeatureBus'
import {
  createIdlePreviewPlaybackState,
  type PreviewPlaybackCommand,
} from '@/features/video/preview/transportClock'
import { emitShellStatus } from '@/shared/lib/shellStatus'
import type { VideoWorkspaceState } from '@/shared/types/desktop'

type UsePreviewTransportCoordinatorOptions = {
  audioMotionSmoothing: number
  onPlaybackStateChange?: (state: VideoWorkspaceState['playback']) => void
  playbackCommand: PreviewPlaybackCommand | null
  previewVolume: number
  selectedMp3Path: string
}

type UsePreviewTransportCoordinatorResult = {
  audioRuntimeRef: MutableRefObject<AudioAnalysisRuntime>
  lastPlaybackReportAtRef: MutableRefObject<number>
  reportPlaybackState: (nextState: VideoWorkspaceState['playback'], force?: boolean) => void
}

export function usePreviewTransportCoordinator({
  audioMotionSmoothing,
  onPlaybackStateChange,
  playbackCommand,
  previewVolume,
  selectedMp3Path,
}: UsePreviewTransportCoordinatorOptions): UsePreviewTransportCoordinatorResult {
  const audioRuntimeRef = useRef<AudioAnalysisRuntime>(createEmptyAudioAnalysisRuntime())
  const lastPlaybackReportRef = useRef<VideoWorkspaceState['playback'] | null>(null)
  const lastPlaybackReportAtRef = useRef(0)
  const handledPlaybackCommandNonceRef = useRef(0)
  const latestPlaybackCommandRef = useRef<PreviewPlaybackCommand | null>(null)
  const pendingPlaybackCommandRef = useRef<PreviewPlaybackCommand | null>(null)

  const reportPlaybackState = useCallback(
    (nextState: VideoWorkspaceState['playback'], force = false) => {
      const previous = lastPlaybackReportRef.current
      const changed =
        !previous ||
        previous.isPlaying !== nextState.isPlaying ||
        previous.isReady !== nextState.isReady ||
        previous.isLoading !== nextState.isLoading ||
        Math.abs(previous.currentTimeSec - nextState.currentTimeSec) > 0.05 ||
        Math.abs(previous.durationSec - nextState.durationSec) > 0.05

      if (!force && !changed) {
        return
      }

      lastPlaybackReportRef.current = nextState
      onPlaybackStateChange?.(nextState)
    },
    [onPlaybackStateChange],
  )

  const tryApplyPlaybackCommand = useCallback(
    (command: PreviewPlaybackCommand | null, runtime: AudioAnalysisRuntime): boolean => {
      if (!command || handledPlaybackCommandNonceRef.current === command.nonce) {
        return false
      }
      if (!runtime.audioElement) {
        pendingPlaybackCommandRef.current = command
        return false
      }

      handledPlaybackCommandNonceRef.current = command.nonce
      pendingPlaybackCommandRef.current = null
      mockableApplyPlaybackCommand({
        command,
        runtime,
        onPlaybackStateChange: (state) => reportPlaybackState(state, true),
        onPlaybackError: (message) => {
          emitShellStatus({
            tone: 'error',
            message,
          })
        },
      })
      return true
    },
    [reportPlaybackState],
  )

  useEffect(() => {
    disposePreviewAudioRuntime(audioRuntimeRef.current)
    audioRuntimeRef.current = createEmptyAudioAnalysisRuntime()
    pendingPlaybackCommandRef.current = null
    reportPlaybackState(createIdlePreviewPlaybackState(), true)

    let cancelled = false
    let teardown = () => undefined

    void (async () => {
      const session = await createPreviewAudioFeatureBus({
        selectedMp3Path,
        audioMotionSmoothing,
        previewVolume,
        onPlaybackStateChange: (state) => reportPlaybackState(state, true),
        onPlaybackError: (message) => {
          emitShellStatus({
            tone: 'error',
            message,
          })
        },
      })
      if (!session) {
        return
      }
      if (cancelled) {
        session.teardown()
        return
      }
      audioRuntimeRef.current = session.runtime
      tryApplyPlaybackCommand(
        pendingPlaybackCommandRef.current ?? latestPlaybackCommandRef.current,
        session.runtime,
      )
      teardown = () => {
        session.teardown()
        audioRuntimeRef.current = createEmptyAudioAnalysisRuntime()
      }
    })()

    return () => {
      cancelled = true
      teardown()
    }
  }, [reportPlaybackState, selectedMp3Path])

  useEffect(() => {
    applyPreviewAudioVolume(audioRuntimeRef.current, previewVolume)
  }, [previewVolume])

  useEffect(() => {
    applyPreviewAudioMotionSmoothing(audioRuntimeRef.current, audioMotionSmoothing)
  }, [audioMotionSmoothing])

  useEffect(() => {
    latestPlaybackCommandRef.current = playbackCommand
    tryApplyPlaybackCommand(playbackCommand, audioRuntimeRef.current)
  }, [playbackCommand, tryApplyPlaybackCommand])

  return {
    audioRuntimeRef,
    lastPlaybackReportAtRef,
    reportPlaybackState,
  }
}

const mockableApplyPlaybackCommand = applyPreviewPlaybackCommand
