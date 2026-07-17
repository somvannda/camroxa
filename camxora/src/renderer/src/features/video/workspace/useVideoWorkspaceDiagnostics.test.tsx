import { act, renderHook } from '@testing-library/react'
import type { QueryClient } from '@tanstack/react-query'
import { describe, expect, it, vi } from 'vitest'

import type { PreviewLifecycleState } from '@/features/video/preview/previewLifecycleState'
import { useVideoWorkspaceDiagnostics } from '@/features/video/workspace/useVideoWorkspaceDiagnostics'

const runningLifecycleState: PreviewLifecycleState = {
  canRecover: false,
  capability: 'webgpu',
  fallbackActive: false,
  label: 'Preview Running',
  lastError: null,
  message: 'Renderer preview is live through the WebGPU compositor.',
  status: 'running',
  webgpuStatus: 'ready',
}

const unsupportedLifecycleState: PreviewLifecycleState = {
  canRecover: false,
  capability: 'css',
  fallbackActive: false,
  label: 'WebGPU Unsupported',
  lastError: 'WebGPU is not available in this renderer process.',
  message: 'This machine does not currently expose WebGPU to the Electron renderer, so the live GPU compositor cannot start in this session.',
  status: 'unsupported',
  webgpuStatus: 'unsupported',
}

const fallbackLifecycleState: PreviewLifecycleState = {
  canRecover: false,
  capability: 'webgpu',
  fallbackActive: true,
  label: 'Fallback Scene Active',
  lastError: null,
  message:
    'Renderer preview is live through WebGPU, but the default engine fallback scene is still active until real template and asset context is available.',
  status: 'fallback-active',
  webgpuStatus: 'ready',
}

describe('useVideoWorkspaceDiagnostics', () => {
  it('derives status badges and exposes real recovery actions for the Video page', async () => {
    const invalidateQueries = vi.fn().mockResolvedValue(undefined)
    const resetLocalDraft = vi.fn()

    const { result } = renderHook(() =>
      useVideoWorkspaceDiagnostics({
        activeTab: 'spectrum',
        backgroundPathDraft: '',
        currentTemplate: {
          logoPath: 'D:/logo.png',
        },
        draftDirtyState: {
          spectrum: true,
          background: false,
          logo: false,
          particles: false,
          text: false,
        },
        patchTemplatePending: false,
        previewLifecycleState: runningLifecycleState,
        previewPlayback: {
          isPlaying: false,
          isReady: true,
          isLoading: false,
          currentTimeSec: 3,
          durationSec: 120,
        },
        previewTrackPath: 'D:/music/preview.mp3',
        queryClient: {
          invalidateQueries,
        } as unknown as QueryClient,
        resetLocalDraft,
        resolvedPipelineInputs: {
          branch: 'long',
          ready: true,
          backgroundPath: 'D:/background.png',
          thumbnailPath: 'D:/thumb.png',
          runDir: 'D:/runs/2026-07-05',
          recommendedTemplateId: 'template-1',
          recommendedTemplateLabel: 'Boss Template',
          sourceMode: 'pipeline',
        },
        saveTemplatePending: false,
        selectedPipelineBranch: 'long',
        selectedPipelineRow: null,
        templateNameDraft: 'Boss Template',
        workspace: {
          templateId: 'template-1',
          templateName: 'Boss Template',
          template: {},
          templates: [],
          outputResolution: '1920x1080',
          previewAspectRatio: { width: 16, height: 9 },
          backgroundPath: 'D:/background.png',
          logoPath: 'D:/logo.png',
          selectedMp3Path: 'D:/music/preview.mp3',
          mp3Directory: '',
          mp3List: [],
          playback: {
            isPlaying: false,
            isReady: true,
            isLoading: false,
            currentTimeSec: 0,
            durationSec: 120,
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
        },
        workspaceDirty: true,
      }),
    )

    expect(result.current.previewStatusLabel).toBe('Preview Running')
    expect(result.current.previewStatusMessage).toContain('WebGPU compositor')
    expect(result.current.saveStatusLabel).toBe('Local Draft Pending')
    expect(result.current.exportStatusLabel).toBe('Export Ready')
    expect(result.current.dirtyDomains.find((item) => item.label === 'Spectrum')?.dirty).toBe(true)

    act(() => {
      result.current.onRemountPreview()
    })

    expect(result.current.previewRuntimeNonce).toBe(1)

    await act(async () => {
      await result.current.onRefreshWorkspace()
    })

    expect(invalidateQueries).toHaveBeenCalledTimes(3)

    act(() => {
      result.current.onResetLocalDraft()
    })

    expect(resetLocalDraft).toHaveBeenCalledTimes(1)
  })

  it('surfaces preview recovering while a remount is in progress', async () => {
    const invalidateQueries = vi.fn().mockResolvedValue(undefined)

    const { result, rerender } = renderHook(
      ({ previewLifecycleState }: { previewLifecycleState: PreviewLifecycleState }) =>
        useVideoWorkspaceDiagnostics({
          activeTab: 'spectrum',
          backgroundPathDraft: '',
          currentTemplate: {},
          draftDirtyState: {
            spectrum: false,
            background: false,
            logo: false,
            particles: false,
            text: false,
          },
          patchTemplatePending: false,
          previewLifecycleState,
          previewPlayback: {
            isPlaying: false,
            isReady: true,
            isLoading: false,
            currentTimeSec: 0,
            durationSec: 10,
          },
          previewTrackPath: 'D:/music/preview.mp3',
          queryClient: {
            invalidateQueries,
          } as unknown as QueryClient,
          resetLocalDraft: vi.fn(),
          resolvedPipelineInputs: {
            branch: 'long',
            ready: false,
            runDir: null,
            sourceMode: 'workspace',
            backgroundPath: null,
            thumbnailPath: null,
            recommendedTemplateId: '',
            recommendedTemplateLabel: '',
          },
          saveTemplatePending: false,
          selectedPipelineBranch: 'long',
          selectedPipelineRow: null,
          templateNameDraft: 'Boss Template',
          workspace: undefined,
          workspaceDirty: false,
        }),
      {
        initialProps: {
          previewLifecycleState: runningLifecycleState,
        },
      },
    )

    act(() => {
      result.current.onRemountPreview()
    })

    expect(result.current.previewStatusLabel).toBe('Preview Recovering')

    rerender({
      previewLifecycleState: {
        canRecover: true,
        capability: 'webgpu',
        fallbackActive: false,
        label: 'Preview Recovering',
        lastError: null,
        message: 'Renderer preview is recovering the WebGPU compositor after a remount or runtime interruption.',
        status: 'recovering',
        webgpuStatus: 'recovering',
      },
    })

    expect(result.current.previewStatusLabel).toBe('Preview Recovering')
  })

  it('surfaces unsupported-preview guidance as operator-facing recovery context', () => {
    const { result } = renderHook(() =>
      useVideoWorkspaceDiagnostics({
        activeTab: 'spectrum',
        backgroundPathDraft: '',
        currentTemplate: {},
        draftDirtyState: {
          spectrum: false,
          background: false,
          logo: false,
          particles: false,
          text: false,
        },
        patchTemplatePending: false,
        previewLifecycleState: unsupportedLifecycleState,
        previewPlayback: {
          isPlaying: false,
          isReady: false,
          isLoading: false,
          currentTimeSec: 0,
          durationSec: 0,
        },
        previewTrackPath: '',
        queryClient: {
          invalidateQueries: vi.fn().mockResolvedValue(undefined),
        } as unknown as QueryClient,
        resetLocalDraft: vi.fn(),
        resolvedPipelineInputs: {
          branch: 'long',
          ready: false,
          runDir: null,
          sourceMode: 'workspace',
          backgroundPath: null,
          thumbnailPath: null,
          recommendedTemplateId: '',
          recommendedTemplateLabel: '',
        },
        saveTemplatePending: false,
        selectedPipelineBranch: 'long',
        selectedPipelineRow: null,
        templateNameDraft: 'Boss Template',
        workspace: undefined,
        workspaceDirty: false,
      }),
    )

    expect(result.current.previewNeedsAttention).toBe(true)
    expect(result.current.previewGuidanceTitle).toContain('unavailable')
    expect(result.current.previewGuidanceItems[0]).toContain('edit the Video workspace')
  })

  it('surfaces fallback guidance for missing background and preview track', () => {
    const { result } = renderHook(() =>
      useVideoWorkspaceDiagnostics({
        activeTab: 'spectrum',
        backgroundPathDraft: '',
        currentTemplate: {},
        draftDirtyState: {
          spectrum: false,
          background: false,
          logo: false,
          particles: false,
          text: false,
        },
        patchTemplatePending: false,
        previewLifecycleState: fallbackLifecycleState,
        previewPlayback: {
          isPlaying: false,
          isReady: false,
          isLoading: false,
          currentTimeSec: 0,
          durationSec: 0,
        },
        previewTrackPath: '',
        queryClient: {
          invalidateQueries: vi.fn().mockResolvedValue(undefined),
        } as unknown as QueryClient,
        resetLocalDraft: vi.fn(),
        resolvedPipelineInputs: {
          branch: 'long',
          ready: false,
          runDir: null,
          sourceMode: 'workspace',
          backgroundPath: null,
          thumbnailPath: null,
          recommendedTemplateId: '',
          recommendedTemplateLabel: '',
        },
        saveTemplatePending: false,
        selectedPipelineBranch: 'long',
        selectedPipelineRow: null,
        templateNameDraft: 'Boss Template',
        workspace: undefined,
        workspaceDirty: false,
      }),
    )

    expect(result.current.previewNeedsAttention).toBe(true)
    expect(result.current.previewGuidanceTitle).toContain('degraded fallback mode')
    expect(result.current.previewGuidanceItems).toEqual(
      expect.arrayContaining([
        expect.stringContaining('Select a background'),
        expect.stringContaining('Select a preview MP3'),
      ]),
    )
  })
})
