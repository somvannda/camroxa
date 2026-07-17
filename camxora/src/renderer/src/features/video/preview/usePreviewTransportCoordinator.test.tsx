import { renderHook, waitFor } from '@testing-library/react'

import { usePreviewTransportCoordinator } from '@/features/video/preview/usePreviewTransportCoordinator'
import type { PreviewPlaybackCommand } from '@/features/video/preview/transportClock'

const mockApplyPreviewAudioVolume = vi.fn()
const mockApplyPreviewAudioMotionSmoothing = vi.fn()
const mockApplyPreviewPlaybackCommand = vi.fn()
const mockCreatePreviewAudioFeatureBus = vi.fn()
const mockDisposePreviewAudioRuntime = vi.fn()
const mockEmitShellStatus = vi.fn()

vi.mock('@/features/video/preview/audioFeatureBus', () => ({
  applyPreviewAudioMotionSmoothing: (...args: unknown[]) => mockApplyPreviewAudioMotionSmoothing(...args),
  applyPreviewAudioVolume: (...args: unknown[]) => mockApplyPreviewAudioVolume(...args),
  applyPreviewPlaybackCommand: (...args: unknown[]) => mockApplyPreviewPlaybackCommand(...args),
  createEmptyAudioAnalysisRuntime: () => ({
    analyser: null,
    frequencyData: null,
    audioContext: null,
    audioElement: null,
    gainNode: null,
    spectrumMapping: null,
    envelope: {
      bassFast: 0,
      bassSlow: 0,
      kick: 0,
      drop: 0,
      level: 0,
      energyBands: null,
      slowBands: null,
      floorBands: null,
      transientBands: null,
      onsetBands: null,
      previousBands: null,
    },
  }),
  createPreviewAudioFeatureBus: (...args: unknown[]) => mockCreatePreviewAudioFeatureBus(...args),
  disposePreviewAudioRuntime: (...args: unknown[]) => mockDisposePreviewAudioRuntime(...args),
}))

vi.mock('@/shared/lib/shellStatus', () => ({
  emitShellStatus: (...args: unknown[]) => mockEmitShellStatus(...args),
}))

describe('usePreviewTransportCoordinator', () => {
  beforeEach(() => {
    mockApplyPreviewAudioMotionSmoothing.mockReset()
    mockApplyPreviewAudioVolume.mockReset()
    mockApplyPreviewPlaybackCommand.mockReset()
    mockCreatePreviewAudioFeatureBus.mockReset()
    mockDisposePreviewAudioRuntime.mockReset()
    mockEmitShellStatus.mockReset()
  })

  it('boots the preview audio session, applies playback commands once per nonce, and updates smoothing/volume without rebuilding', async () => {
    const runtime = {
      analyser: null,
      frequencyData: null,
      audioContext: {} as AudioContext,
      audioElement: {} as HTMLAudioElement,
      gainNode: null,
      spectrumMapping: null,
      envelope: {
        bassFast: 0,
        bassSlow: 0,
        kick: 0,
        drop: 0,
        level: 0,
        energyBands: null,
        slowBands: null,
        floorBands: null,
        transientBands: null,
        onsetBands: null,
        previousBands: null,
      },
    }
    const teardown = vi.fn()
    type HookProps = {
      audioMotionSmoothing: number
      playbackCommand: PreviewPlaybackCommand | null
      previewVolume: number
    }
    const playCommand: PreviewPlaybackCommand = { type: 'play', nonce: 1 }

    mockCreatePreviewAudioFeatureBus.mockResolvedValue({
      runtime,
      teardown,
    })

    const onPlaybackStateChange = vi.fn()
    const { result, rerender, unmount } = renderHook(
      (props: HookProps) =>
        usePreviewTransportCoordinator({
          audioMotionSmoothing: props.audioMotionSmoothing,
          onPlaybackStateChange,
          playbackCommand: props.playbackCommand,
          previewVolume: props.previewVolume,
          selectedMp3Path: 'D:/song.mp3',
        }),
      {
        initialProps: {
          audioMotionSmoothing: 0.8,
          playbackCommand: null,
          previewVolume: 0.7,
        } as HookProps,
      },
    )

    await waitFor(() => {
      expect(mockCreatePreviewAudioFeatureBus).toHaveBeenCalledWith(
        expect.objectContaining({
          audioMotionSmoothing: 0.8,
          previewVolume: 0.7,
          selectedMp3Path: 'D:/song.mp3',
        }),
      )
      expect(result.current.audioRuntimeRef.current).toBe(runtime)
    })

    rerender({
      audioMotionSmoothing: 0.8,
      playbackCommand: playCommand,
      previewVolume: 0.7,
    } as HookProps)

    await waitFor(() => {
      expect(mockApplyPreviewPlaybackCommand).toHaveBeenCalledTimes(1)
      expect(mockApplyPreviewPlaybackCommand).toHaveBeenCalledWith(
        expect.objectContaining({
          command: playCommand,
          runtime,
        }),
      )
    })

    rerender({
      audioMotionSmoothing: 0.8,
      playbackCommand: playCommand,
      previewVolume: 0.7,
    } as HookProps)

    await waitFor(() => {
      expect(mockApplyPreviewPlaybackCommand).toHaveBeenCalledTimes(1)
    })

    rerender({
      audioMotionSmoothing: 0.42,
      playbackCommand: playCommand,
      previewVolume: 0.35,
    } as HookProps)

    await waitFor(() => {
      expect(mockCreatePreviewAudioFeatureBus).toHaveBeenCalledTimes(1)
      expect(mockApplyPreviewAudioMotionSmoothing).toHaveBeenCalledWith(runtime, 0.42)
      expect(mockApplyPreviewAudioVolume).toHaveBeenCalledWith(runtime, 0.35)
    })

    expect(mockApplyPreviewAudioVolume).toHaveBeenCalled()
    expect(mockApplyPreviewAudioMotionSmoothing).toHaveBeenCalled()

    unmount()

    expect(teardown).toHaveBeenCalledTimes(1)
  })

  it('replays a queued playback command after the audio runtime becomes available', async () => {
    const runtime = {
      analyser: null,
      frequencyData: null,
      audioContext: {} as AudioContext,
      audioElement: {} as HTMLAudioElement,
      gainNode: null,
      spectrumMapping: null,
      envelope: {
        bassFast: 0,
        bassSlow: 0,
        kick: 0,
        drop: 0,
        level: 0,
        energyBands: null,
        slowBands: null,
        floorBands: null,
        transientBands: null,
        onsetBands: null,
        previousBands: null,
      },
    }
    const teardown = vi.fn()
    const seekCommand: PreviewPlaybackCommand = { type: 'seek', timeSec: 12.5, nonce: 7 }

    let resolveSession: ((value: { runtime: typeof runtime; teardown: typeof teardown }) => void) | null = null
    mockCreatePreviewAudioFeatureBus.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveSession = resolve
        }),
    )

    const { rerender } = renderHook(
      ({ playbackCommand }: { playbackCommand: PreviewPlaybackCommand | null }) =>
        usePreviewTransportCoordinator({
          audioMotionSmoothing: 0.6,
          onPlaybackStateChange: vi.fn(),
          playbackCommand,
          previewVolume: 0,
          selectedMp3Path: 'D:/song.mp3',
        }),
      {
        initialProps: {
          playbackCommand: null,
        },
      },
    )

    rerender({ playbackCommand: seekCommand })

    await waitFor(() => {
      expect(mockApplyPreviewPlaybackCommand).not.toHaveBeenCalled()
    })

    resolveSession?.({
      runtime,
      teardown,
    })

    await waitFor(() => {
      expect(mockApplyPreviewPlaybackCommand).toHaveBeenCalledTimes(1)
      expect(mockApplyPreviewPlaybackCommand).toHaveBeenCalledWith(
        expect.objectContaining({
          command: seekCommand,
          runtime,
        }),
      )
    })
  })
})
