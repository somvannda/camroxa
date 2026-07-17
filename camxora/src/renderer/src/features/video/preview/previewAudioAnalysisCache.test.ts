import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { PreviewAudioReactiveFeatureTimeline } from '@/features/video/preview/audioReactiveTimeline'
import {
  loadCachedPreviewAudioReactiveTimeline,
  storeCachedPreviewAudioReactiveTimeline,
} from '@/features/video/preview/previewAudioAnalysisCache'

const mockGetAudioAnalysisCache = vi.fn()
const mockSetAudioAnalysisCache = vi.fn()

vi.mock('@/shared/api/desktop', () => ({
  getDesktopApi: () => ({
    video: {
      getAudioAnalysisCache: (...args: unknown[]) => mockGetAudioAnalysisCache(...args),
      setAudioAnalysisCache: (...args: unknown[]) => mockSetAudioAnalysisCache(...args),
    },
  }),
}))

function createTimeline(): PreviewAudioReactiveFeatureTimeline {
  return {
    durationSec: 1,
    frameRate: 30,
    frames: [
      {
        timeSec: 0,
        energyBands: new Float32Array([0.1, 0.2]),
        peakHoldBands: new Float32Array([0.3, 0.4]),
        transientBands: new Float32Array([0.5, 0.6]),
        onsetBands: new Float32Array([0.7, 0.8]),
        framePeak: 0.4,
        averageEnergy: 0.2,
        averageTransient: 0.15,
        averageOnset: 0.17,
        level: 0.4,
        kick: 0.3,
        drop: 0.25,
        reactiveEnergy: 0.35,
        bass: 0.2,
        mid: 0.1,
        treble: 0.05,
        energy: 0.22,
        onset: 0.18,
        transient: 0.16,
        beat: 1,
      },
    ],
  }
}

describe('previewAudioAnalysisCache', () => {
  beforeEach(() => {
    mockGetAudioAnalysisCache.mockReset()
    mockSetAudioAnalysisCache.mockReset()
  })

  it('loads and restores a cached preview audio reactive timeline', async () => {
    mockGetAudioAnalysisCache.mockResolvedValue(
      JSON.stringify({
        version: 1,
        sourcePath: 'D:/music/song.mp3',
        timeline: {
          durationSec: 1,
          frameRate: 30,
          frames: [
            {
              ...createTimeline().frames[0],
              energyBands: [0.1, 0.2],
              peakHoldBands: [0.3, 0.4],
              transientBands: [0.5, 0.6],
              onsetBands: [0.7, 0.8],
            },
          ],
        },
      }),
    )

    const restored = await loadCachedPreviewAudioReactiveTimeline('D:/music/song.mp3')

    expect(restored).not.toBeNull()
    expect(restored?.frames[0]?.energyBands[0]).toBeCloseTo(0.1, 5)
    expect(restored?.frames[0]?.energyBands[1]).toBeCloseTo(0.2, 5)
    expect(restored?.frames[0]?.beat).toBe(1)
    expect(mockGetAudioAnalysisCache).toHaveBeenCalledWith({ sourcePath: 'D:/music/song.mp3' })
  })

  it('stores serialized preview audio reactive timelines through the desktop cache bridge', async () => {
    mockSetAudioAnalysisCache.mockResolvedValue(true)

    const stored = await storeCachedPreviewAudioReactiveTimeline('D:/music/song.mp3', createTimeline())

    expect(stored).toBe(true)
    expect(mockSetAudioAnalysisCache).toHaveBeenCalledTimes(1)
    expect(mockSetAudioAnalysisCache.mock.calls[0]?.[0]).toMatchObject({
      sourcePath: 'D:/music/song.mp3',
    })
    expect(String(mockSetAudioAnalysisCache.mock.calls[0]?.[0]?.payload ?? '')).toContain('"version":1')
  })
})
