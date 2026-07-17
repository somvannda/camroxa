import { act, renderHook } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { useVideoWorkspaceShell } from '@/features/video/workspace/useVideoWorkspaceShell'
import type { VideoWorkspaceState } from '@/shared/types/desktop'

function buildWorkspaceState(overrides?: Partial<VideoWorkspaceState>): VideoWorkspaceState {
  return {
    template: {
      style: 'straight-bars',
      spectrumEnabled: true,
      layers: [],
      textOverlays: [],
    },
    templateId: 'template-1',
    templateName: 'Studio Template',
    templates: [],
    outputResolution: '1920x1080',
    previewAspectRatio: {
      width: 16,
      height: 9,
    },
    backgroundPath: 'D:/background-a.png',
    logoPath: 'D:/logo.png',
    selectedMp3Path: '',
    mp3Directory: '',
    mp3List: [],
    playback: {
      isPlaying: false,
      isReady: false,
      isLoading: false,
      currentTimeSec: 0,
      durationSec: 0,
    },
    export: {
      running: false,
      branch: null,
      workers: 1,
      autoMerge: false,
      mergeRunning: false,
      currentStatus: 'idle',
      outputDir: null,
      totalJobs: 0,
      completedJobs: 0,
      lastOutputPath: null,
      lastMergedOutputPath: null,
    },
    ui: {
      previewTitle: 'Preview',
      livePreviewOpen: false,
      source: 'python-local',
      notes: [],
    },
    ...overrides,
  }
}

describe('useVideoWorkspaceShell', () => {
  it('hydrates shell selections from workspace context and first available items', () => {
    const { result } = renderHook(() =>
      useVideoWorkspaceShell({
        workspace: buildWorkspaceState({
          templateId: 'template-9',
          templateName: 'Boss Template',
          backgroundPath: 'D:/preview-bg.png',
        }),
        previewTrackPath: '',
        layerKeys: ['3', '5'],
        pipelineRunKeys: ['run-a', 'run-b'],
        textOverlayCount: 2,
      }),
    )

    expect(result.current.selectedTemplateId).toBe('template-9')
    expect(result.current.backgroundPathDraft).toBe('D:/preview-bg.png')
    expect(result.current.selectedPipelineRunKey).toBe('run-a')
    expect(result.current.selectedLayerKey).toBe('3')
    expect(result.current.selectedTextOverlayKey).toBe('0')
  })

  it('preserves manual background staging and issues autoplay once the current preview track is ready', () => {
    const { result, rerender } = renderHook(
      ({ workspace, previewTrackPath }) =>
        useVideoWorkspaceShell({
          workspace,
          previewTrackPath,
          layerKeys: ['0'],
          pipelineRunKeys: ['run-a'],
          textOverlayCount: 1,
        }),
      {
        initialProps: {
          workspace: buildWorkspaceState(),
          previewTrackPath: 'D:/music/song-a.mp3',
        },
      },
    )

    expect(result.current.previewPlayback.isLoading).toBe(true)

    act(() => {
      result.current.setBackgroundPathDraft('D:/manual-preview.png')
    })

    rerender({
      workspace: buildWorkspaceState({
        backgroundPath: 'D:/background-b.png',
      }),
      previewTrackPath: 'D:/music/song-a.mp3',
    })

    expect(result.current.backgroundPathDraft).toBe('D:/manual-preview.png')

    act(() => {
      result.current.queuePreviewAutoplay('D:/music/song-a.mp3')
      result.current.setPreviewPlayback({
        isPlaying: false,
        isReady: true,
        isLoading: false,
        currentTimeSec: 0,
        durationSec: 180,
      })
    })

    expect(result.current.previewPlaybackCommand?.type).toBe('play')
  })
})
