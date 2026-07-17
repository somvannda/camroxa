import { act, renderHook } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { useVideoWorkspaceDraft } from '@/features/video/workspace/useVideoWorkspaceDraft'
import type { VideoWorkspaceState } from '@/shared/types/desktop'

function buildWorkspaceState(overrides?: Partial<VideoWorkspaceState>): VideoWorkspaceState {
  return {
    template: {
      style: 'liquid',
      spectrumEnabled: true,
      layers: [{ id: 'layer-1' }],
      textOverlays: [],
      audioSettings: {
        inputGain: 1,
        barHeight: 1,
        bandContrast: 1,
        transientFocus: 1,
        kickImpact: 0,
        bassEmphasis: 1,
        trebleShimmer: 1,
        peakHoldBlend: 0,
        motionSmoothing: 0.8,
        flyingGlowWingMotionSpeed: 1,
        flyingGlowWingRelease: 0.9,
      },
      position: {
        anchor: 'center',
        x: 0,
        y: 0,
      },
      previewBindings: {
        spectrumAttachToLogo: true,
        spectrumLogoGap: 24,
      },
      backgroundSettings: {
        fitMode: 'cover',
        userScale: 1,
        brightness: 1,
        reactivity: 0,
        smoothing: 0.8,
        motionMode: 'none',
        motionZoomStrength: 1,
        motionVibrateStrength: 1,
      },
      effects: {
        vignette: { enabled: false },
        smoke: { enabled: false },
      },
      logoSettings: {
        enabled: true,
        spinEnabled: false,
        spinDirection: 'cw',
        spinSpeed: 0,
        circleMask: true,
        size: 200,
        opacity: 1,
        reactivity: 0,
        smoothing: 0.75,
      },
      particlesSettings: {
        enabled: true,
        maxCount: 200,
        spawnRate: 100,
        lifetimeSec: 1.6,
        speed: 1,
        reactivity: 0.1,
        smoothing: 0.65,
        spawnMode: 'always',
        spawnTrigger: 'both',
        spawnThreshold: 0.15,
        variant: 'classic',
        spawnArea: 'centerRing',
        sizeJitter: 0,
        drift: 0,
        swirl: 0,
        style: 'dot',
        size: 2,
        opacity: 0.35,
        color: '#ffffff',
        reactColor: '#ffffff',
        reactStrength: 0.65,
      },
    },
    templateId: 'template-1',
    templateName: 'Bass Drive',
    templates: [],
    outputResolution: '1920x1080',
    previewAspectRatio: {
      width: 16,
      height: 9,
    },
    backgroundPath: 'D:/background.png',
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
      previewTitle: 'Preview: Bass Drive',
      livePreviewOpen: false,
      source: 'python-local',
      notes: [],
    },
    ...overrides,
  }
}

describe('useVideoWorkspaceDraft', () => {
  it('preserves the local spectrum draft during same-template workspace refreshes', () => {
    window.localStorage.clear()
    const onHydrated = vi.fn()
    const workspace = buildWorkspaceState()

    const { result, rerender } = renderHook(
      ({ currentWorkspace }) =>
        useVideoWorkspaceDraft({
          workspace: currentWorkspace,
          storagePrefix: 'camxora.video.workspace-draft',
          onHydrated,
        }),
      {
        initialProps: {
          currentWorkspace: workspace,
        },
      },
    )

    expect(result.current.templateDraft?.style).toBe('liquid-mass')
    expect(result.current.templateNameDraft).toBe('Bass Drive')

    act(() => {
      result.current.setTemplateDraft({
        ...(result.current.templateDraft ?? (() => {
          throw new Error('Expected hydrated draft')
        })()),
        style: 'straight-bars',
      })
      result.current.setTemplateNameDraft('Locally Renamed')
    })

    rerender({
      currentWorkspace: buildWorkspaceState({
        template: {
          ...workspace.template,
          style: 'liquid',
        },
      }),
    })

    expect(result.current.templateDraft?.style).toBe('straight-bars')
    expect(result.current.templateNameDraft).toBe('Locally Renamed')
    expect(onHydrated).toHaveBeenCalledTimes(1)
  })

  it('rehydrates the local draft when the template id changes', () => {
    window.localStorage.clear()
    const onHydrated = vi.fn()

    const { result, rerender } = renderHook(
      ({ currentWorkspace }) =>
        useVideoWorkspaceDraft({
          workspace: currentWorkspace,
          storagePrefix: 'camxora.video.workspace-draft',
          onHydrated,
        }),
      {
        initialProps: {
          currentWorkspace: buildWorkspaceState(),
        },
      },
    )

    act(() => {
      result.current.setTemplateDraft({
        ...(result.current.templateDraft ?? (() => {
          throw new Error('Expected hydrated draft')
        })()),
        style: 'straight-bars',
      })
      result.current.setTemplateNameDraft('Local Template Name')
    })

    rerender({
      currentWorkspace: buildWorkspaceState({
        templateId: 'template-2',
        templateName: 'Glow',
        template: {
          ...buildWorkspaceState().template,
          style: 'flying-glow',
        },
      }),
    })

    expect(result.current.templateDraft?.style).toBe('flying-glow')
    expect(result.current.templateNameDraft).toBe('Glow')
    expect(onHydrated).toHaveBeenCalledTimes(2)
  })

  it('resets the local workspace draft back to the persisted template state', () => {
    window.localStorage.clear()

    const { result } = renderHook(() =>
      useVideoWorkspaceDraft({
        workspace: buildWorkspaceState(),
        storagePrefix: 'camxora.video.workspace-draft',
      }),
    )

    act(() => {
      result.current.setTemplateDraft({
        ...(result.current.templateDraft ?? (() => {
          throw new Error('Expected hydrated draft')
        })()),
        style: 'straight-bars',
      })
      result.current.setTemplateNameDraft('Boss Local Draft')
    })

    expect(result.current.templateDraft?.style).toBe('straight-bars')
    expect(result.current.templateNameDraft).toBe('Boss Local Draft')

    act(() => {
      result.current.resetLocalDraft()
    })

    expect(result.current.templateDraft?.style).toBe('liquid-mass')
    expect(result.current.templateNameDraft).toBe('Bass Drive')
  })
})
