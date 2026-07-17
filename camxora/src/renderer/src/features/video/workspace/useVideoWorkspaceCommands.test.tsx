import { act, renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import { buildVideoTemplateDraft } from '@/features/video/core/contracts/videoTemplateDraft'
import { useVideoWorkspaceCommands } from '@/features/video/workspace/useVideoWorkspaceCommands'
import type { DesktopApi, VideoWorkspaceState } from '@/shared/types/desktop'

const mockApiPatchSettings = vi.fn()

vi.mock('@/shared/api/platformEndpoints', async () => {
  const actual = await vi.importActual('@/shared/api/platformEndpoints')
  return {
    ...actual,
    apiPatchSettings: (...args: unknown[]) => mockApiPatchSettings(...args),
  }
})

function buildWorkspaceState(overrides?: Partial<VideoWorkspaceState>): VideoWorkspaceState {
  return {
    template: {},
    templateId: 'template-1',
    templateName: 'Template A',
    templates: [],
    outputResolution: '1920x1080',
    previewAspectRatio: { width: 16, height: 9 },
    backgroundPath: '',
    logoPath: '',
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

function buildDesktopApi(): DesktopApi {
  return {
    getAppMeta: vi.fn(),
    isSplash: false,
    splashDone: vi.fn(),
    bootstrap: {
      reportProgress: vi.fn(),
      done: vi.fn(),
      onProgress: vi.fn(() => () => undefined),
    },
    windowControls: {
      minimize: vi.fn(),
      toggleMaximize: vi.fn(),
      isMaximized: vi.fn(),
      close: vi.fn(),
    },
    secureStorage: {
      get: vi.fn(),
      set: vi.fn(),
      remove: vi.fn(),
      clear: vi.fn(),
    },
    files: {
      selectFile: vi.fn(),
      selectPath: vi.fn(),
      readFileAsBase64: vi.fn(),
      saveBase64File: vi.fn(),
      ensureDirectory: vi.fn(),
      openPath: vi.fn(),
      openExternalUrl: vi.fn(),
      listDirectoryEntries: vi.fn(),
      listDirectoryImages: vi.fn(),
      downloadAndExtractZip: vi.fn(),
      downloadMusicTracks: vi.fn(),
    },
    effectPacks: {
      listCatalog: vi.fn().mockResolvedValue({ items: [] }),
      installFromUrl: vi.fn(),
      installFromFile: vi.fn(),
      setEnabled: vi.fn(),
      activateVersion: vi.fn(),
      removeVersion: vi.fn(),
    },
    video: {
      getWorkspaceState: vi.fn(),
      setTemplate: vi.fn().mockResolvedValue(buildWorkspaceState({ templateId: 'template-2' })),
      deleteTemplate: vi.fn().mockResolvedValue(buildWorkspaceState({ templateId: 'template-2' })),
      setOutputResolution: vi.fn(),
      setBackgroundPath: vi.fn().mockResolvedValue(buildWorkspaceState({ backgroundPath: 'D:/bg.png' })),
      setLogoPath: vi.fn(),
      setMp3Path: vi.fn(),
      patchTemplate: vi.fn(),
      getAudioAnalysisCache: vi.fn(),
      setAudioAnalysisCache: vi.fn(),
      startManualExport: vi.fn(),
      startPipelineExport: vi.fn(),
      stopExport: vi.fn(),
      onWorkspaceEvent: vi.fn(() => () => undefined),
    },
    videoPreview: {
      open: vi.fn(),
      close: vi.fn(),
      setHostBounds: vi.fn(),
      patchTemplate: vi.fn(),
      setAssets: vi.fn(),
      onEvent: vi.fn(() => () => undefined),
    },
  }
}

describe('useVideoWorkspaceCommands', () => {
  beforeEach(() => {
    mockApiPatchSettings.mockReset()
    mockApiPatchSettings.mockResolvedValue({})
    vi.restoreAllMocks()
  })

  it('changes template selection through the desktop bridge only when the value changes', async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { gcTime: Infinity, retry: false } } })
    const desktopApi = buildDesktopApi()
    const setSelectedTemplateId = vi.fn()
    const templateDraft = buildVideoTemplateDraft({}, { logoPath: '' })

    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    )

    const { result } = renderHook(
      () =>
        useVideoWorkspaceCommands({
          desktopApi,
          queryClient,
          workspace: buildWorkspaceState({ templateId: 'template-1' }),
          resolvedPipelineInputs: {
            branch: 'long',
            ready: false,
            runDir: '',
            sourceMode: null,
            backgroundPath: '',
            thumbnailPath: null,
            recommendedTemplateId: null,
            recommendedTemplateLabel: 'Long template',
          },
          selectedPipelineBranch: 'long',
          selectedPipelineRow: null,
          previewTemplate: {},
          previewTrackPath: '',
          previewPlayback: { isReady: false, isLoading: false },
          issuePreviewPlaybackCommand: vi.fn(),
          queuePreviewAutoplay: vi.fn(),
          setBackgroundPathDraft: vi.fn(),
          setSelectedTemplateId,
          templateDraft,
        }),
      { wrapper },
    )

    act(() => {
      result.current.handleTemplateSelectionChange('template-1')
    })

    expect(desktopApi.video.setTemplate).not.toHaveBeenCalled()

    act(() => {
      result.current.handleTemplateSelectionChange('template-2')
    })

    await waitFor(() => {
      expect(desktopApi.video.setTemplate).toHaveBeenCalledWith('template-2')
    })
    expect(setSelectedTemplateId).toHaveBeenCalledWith('template-2')
  })

  it('selects a background, stages it locally, and syncs workspace cache', async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { gcTime: Infinity, retry: false } } })
    const desktopApi = buildDesktopApi()
    const setBackgroundPathDraft = vi.fn()
    const nextWorkspace = buildWorkspaceState({ backgroundPath: 'D:/backgrounds/custom.png' })
    const templateDraft = buildVideoTemplateDraft({}, { logoPath: '' })

    vi.mocked(desktopApi.files.selectFile).mockResolvedValue('D:/backgrounds/custom.png')
    vi.mocked(desktopApi.video.setBackgroundPath).mockResolvedValue(nextWorkspace)

    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    )

    const { result } = renderHook(
      () =>
        useVideoWorkspaceCommands({
          desktopApi,
          queryClient,
          workspace: buildWorkspaceState(),
          resolvedPipelineInputs: {
            branch: 'long',
            ready: false,
            runDir: '',
            sourceMode: null,
            backgroundPath: '',
            thumbnailPath: null,
            recommendedTemplateId: null,
            recommendedTemplateLabel: 'Long template',
          },
          selectedPipelineBranch: 'long',
          selectedPipelineRow: null,
          previewTemplate: {},
          previewTrackPath: '',
          previewPlayback: { isReady: false, isLoading: false },
          issuePreviewPlaybackCommand: vi.fn(),
          queuePreviewAutoplay: vi.fn(),
          setBackgroundPathDraft,
          setSelectedTemplateId: vi.fn(),
          templateDraft,
        }),
      { wrapper },
    )

    await act(async () => {
      await result.current.handleSelectBackground()
    })

    expect(setBackgroundPathDraft).toHaveBeenCalledWith('D:/backgrounds/custom.png')
    expect(desktopApi.video.setBackgroundPath).toHaveBeenCalledWith('D:/backgrounds/custom.png')
    expect(mockApiPatchSettings).toHaveBeenCalledWith({ videoRenderBackgroundPath: 'D:/backgrounds/custom.png' })
    expect(queryClient.getQueryData(['video-workspace'])).toEqual(nextWorkspace)
  })

  it('deletes the selected template only after confirmation', async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { gcTime: Infinity, retry: false } } })
    const desktopApi = buildDesktopApi()
    const setSelectedTemplateId = vi.fn()
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
    const templateDraft = buildVideoTemplateDraft({}, { logoPath: '' })

    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    )

    const { result } = renderHook(
      () =>
        useVideoWorkspaceCommands({
          desktopApi,
          queryClient,
          workspace: buildWorkspaceState({
            templateId: 'template-1',
            templateName: 'Template A',
            templates: [
              { id: 'template-1', name: 'Template A', kind: null, updatedAt: null },
              { id: 'template-2', name: 'Template B', kind: null, updatedAt: null },
            ],
          }),
          resolvedPipelineInputs: {
            branch: 'long',
            ready: false,
            runDir: '',
            sourceMode: null,
            backgroundPath: '',
            thumbnailPath: null,
            recommendedTemplateId: null,
            recommendedTemplateLabel: 'Long template',
          },
          selectedPipelineBranch: 'long',
          selectedPipelineRow: null,
          previewTemplate: {},
          previewTrackPath: '',
          previewPlayback: { isReady: false, isLoading: false },
          issuePreviewPlaybackCommand: vi.fn(),
          queuePreviewAutoplay: vi.fn(),
          setBackgroundPathDraft: vi.fn(),
          setSelectedTemplateId,
          templateDraft,
        }),
      { wrapper },
    )

    await act(async () => {
      await result.current.handleDeleteTemplate()
    })

    expect(confirmSpy).toHaveBeenCalled()
    expect(desktopApi.video.deleteTemplate).toHaveBeenCalledWith('template-1')
    expect(setSelectedTemplateId).toHaveBeenCalledWith('template-2')
  })

  it('builds and sends a manual export scene from the live preview draft', async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { gcTime: Infinity, retry: false } } })
    const desktopApi = buildDesktopApi()
    const workspace = buildWorkspaceState({
      backgroundPath: 'D:/backgrounds/live.png',
      logoPath: 'D:/logos/saved.png',
      selectedMp3Path: 'D:/audio/workspace.mp3',
      outputResolution: '2560x1440',
    })
    const templateDraft = {
      ...buildVideoTemplateDraft({ style: 'flying-glow' }, { logoPath: workspace.logoPath }),
      particlesSpeed: 11.5,
      logoPath: 'D:/logos/live-draft.png',
    }
    vi.mocked(desktopApi.video.startManualExport).mockResolvedValue(workspace)

    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    )

    const { result } = renderHook(
      () =>
        useVideoWorkspaceCommands({
          desktopApi,
          queryClient,
          workspace,
          resolvedPipelineInputs: {
            branch: 'long',
            ready: false,
            runDir: '',
            sourceMode: null,
            backgroundPath: '',
            thumbnailPath: null,
            recommendedTemplateId: null,
            recommendedTemplateLabel: 'Long template',
          },
          selectedPipelineBranch: 'long',
          selectedPipelineRow: null,
          previewTemplate: {
            style: 'flying-glow',
            layers: [{ id: 'layer-1' }],
          },
          previewTrackPath: 'D:/audio/live-preview.mp3',
          previewPlayback: { isReady: true, isLoading: false },
          issuePreviewPlaybackCommand: vi.fn(),
          queuePreviewAutoplay: vi.fn(),
          setBackgroundPathDraft: vi.fn(),
          setSelectedTemplateId: vi.fn(),
          templateDraft,
        }),
      { wrapper },
    )

    await act(async () => {
      await result.current.startManualExport()
    })

    expect(desktopApi.video.startManualExport).toHaveBeenCalledTimes(1)
    expect(desktopApi.video.startManualExport).toHaveBeenCalledWith({
      scene: expect.objectContaining({
        mode: 'manual',
        template: {
          style: 'flying-glow',
          layers: [{ id: 'layer-1' }],
        },
        assets: expect.objectContaining({
          backgroundPath: 'D:/backgrounds/live.png',
          logoPath: 'D:/logos/live-draft.png',
          audioPath: 'D:/audio/live-preview.mp3',
        }),
        output: expect.objectContaining({
          resolution: '2560x1440',
          width: 2560,
          height: 1440,
          fps: 60,
        }),
        context: expect.objectContaining({
          templateId: 'template-1',
          draftSource: 'live',
        }),
      }),
    })
  })
})
