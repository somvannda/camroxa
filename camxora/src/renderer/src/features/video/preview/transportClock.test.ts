import {
  buildPreviewPlaybackState,
  createIdlePreviewPlaybackState,
} from '@/features/video/preview/transportClock'

describe('transportClock', () => {
  it('builds an idle playback snapshot by default', () => {
    expect(createIdlePreviewPlaybackState()).toEqual({
      isPlaying: false,
      isReady: false,
      isLoading: false,
      currentTimeSec: 0,
      durationSec: 0,
    })
  })

  it('derives playback state from the current media element snapshot', () => {
    const state = buildPreviewPlaybackState({
      paused: false,
      ended: false,
      readyState: 3,
      currentTime: 12.5,
      duration: 180,
    })

    expect(state).toEqual({
      isPlaying: true,
      isReady: true,
      isLoading: false,
      currentTimeSec: 12.5,
      durationSec: 180,
    })
  })

  it('allows explicit overrides for stop and seek snapshots', () => {
    const stopped = buildPreviewPlaybackState(
      {
        paused: true,
        ended: false,
        readyState: 4,
        currentTime: 52,
        duration: 180,
      },
      { currentTimeSec: 0, isPlaying: false },
    )

    expect(stopped.currentTimeSec).toBe(0)
    expect(stopped.isPlaying).toBe(false)
    expect(stopped.durationSec).toBe(180)
  })
})
