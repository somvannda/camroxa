import type { VideoWorkspaceState } from '@/shared/types/desktop'

export type PreviewPlaybackCommandInput =
  | { type: 'play' }
  | { type: 'pause' }
  | { type: 'stop' }
  | { type: 'seek'; timeSec: number }

export type PreviewPlaybackCommand = PreviewPlaybackCommandInput & { nonce: number }

type PreviewAudioElementSnapshot = Pick<
  HTMLAudioElement,
  'paused' | 'ended' | 'readyState' | 'currentTime' | 'duration'
>

export function createIdlePreviewPlaybackState(
  overrides?: Partial<VideoWorkspaceState['playback']>,
): VideoWorkspaceState['playback'] {
  return {
    isPlaying: false,
    isReady: false,
    isLoading: false,
    currentTimeSec: 0,
    durationSec: 0,
    ...overrides,
  }
}

export function buildPreviewPlaybackState(
  audioElement: PreviewAudioElementSnapshot,
  overrides?: Partial<VideoWorkspaceState['playback']>,
): VideoWorkspaceState['playback'] {
  return {
    isPlaying: !audioElement.paused && !audioElement.ended,
    isReady: audioElement.readyState >= 1,
    isLoading: audioElement.readyState < 2,
    currentTimeSec: Number.isFinite(audioElement.currentTime) ? audioElement.currentTime : 0,
    durationSec: Number.isFinite(audioElement.duration) ? audioElement.duration : 0,
    ...overrides,
  }
}
