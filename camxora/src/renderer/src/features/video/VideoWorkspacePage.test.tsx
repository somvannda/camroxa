import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import { VideoWorkspacePage } from '@/features/video/VideoWorkspacePage'

window.HTMLElement.prototype.scrollIntoView = vi.fn()

const mockUseVideoWorkspaceQuery = vi.fn()
const mockUseProgressRowsQuery = vi.fn()
const mockPatchTemplate = vi.fn()
const mockSetTemplate = vi.fn()
const mockDeleteTemplate = vi.fn()
const mockSetOutputResolution = vi.fn()
const mockSetBackgroundPath = vi.fn()
const mockSetLogoPath = vi.fn()
const mockStartPipelineExport = vi.fn()
const mockStopExport = vi.fn()
const mockOpenPath = vi.fn()
const mockSelectFile = vi.fn()
const mockReadFileAsBase64 = vi.fn()
const mockApiPatchSettings = vi.fn()
const mockDesktopApi = {
  files: {
    selectFile: (...args: unknown[]) => mockSelectFile(...args),
    readFileAsBase64: (...args: unknown[]) => mockReadFileAsBase64(...args),
    openPath: (...args: unknown[]) => mockOpenPath(...args),
  },
  video: {
    patchTemplate: (...args: unknown[]) => mockPatchTemplate(...args),
    setTemplate: (...args: unknown[]) => mockSetTemplate(...args),
    deleteTemplate: (...args: unknown[]) => mockDeleteTemplate(...args),
    setOutputResolution: (...args: unknown[]) => mockSetOutputResolution(...args),
    setBackgroundPath: (...args: unknown[]) => mockSetBackgroundPath(...args),
    setLogoPath: (...args: unknown[]) => mockSetLogoPath(...args),
    startPipelineExport: (...args: unknown[]) => mockStartPipelineExport(...args),
    stopExport: (...args: unknown[]) => mockStopExport(...args),
  },
}

vi.mock('@/features/video/useVideoWorkspaceQuery', () => ({
  useVideoWorkspaceQuery: () => mockUseVideoWorkspaceQuery(),
}))

vi.mock('@/features/shell/useProgressRowsQuery', () => ({
  useProgressRowsQuery: (...args: unknown[]) => mockUseProgressRowsQuery(...args),
}))

vi.mock('@/features/video/RendererVideoPreview', () => ({
  RendererVideoPreview: (props: { previewVolume?: number }) =>
    (props.previewVolume ?? 1) < 0.01 ? (
      <div data-testid="renderer-video-preview-particle-mini" />
    ) : (
      <div data-testid="renderer-video-preview" />
    ),
}))

vi.mock('@/shared/api/desktop', () => ({
  getDesktopApi: () => mockDesktopApi,
}))

vi.mock('@/shared/api/platformEndpoints', async () => {
  const actual = await vi.importActual('@/shared/api/platformEndpoints')
  return {
    ...actual,
    apiPatchSettings: (...args: unknown[]) => mockApiPatchSettings(...args),
    apiListProfiles: vi.fn().mockResolvedValue([
      {
        id: 'profile-1',
        user_id: 'user-1',
        name: 'Primary',
        folder_name: 'Primary',
        run_prefix: 'PRI',
        logo_path: 'D:/MusicGenerator/logos/logo.png',
        video_template_id: 'template-1',
        reel_template_id: 'template-2',
        output_resolution: '1920x1080',
        image_config: {},
        youtube_config: {},
      },
    ]),
  }
})

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        gcTime: Infinity,
        retry: false,
      },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <VideoWorkspacePage />
    </QueryClientProvider>,
  )
}

async function activateWorkspaceTab(name: RegExp, readyText: RegExp) {
  const matchingButtons = screen.getAllByRole('button', { name })
  for (const button of matchingButtons) {
    fireEvent.click(button)
    if (screen.queryByText(readyText)) {
      return
    }
  }
  throw new Error(`Workspace tab not found for ${name}`)
}

describe('VideoWorkspacePage', () => {
  beforeEach(() => {
    window.localStorage.clear()
    window.sessionStorage.clear()
    mockSelectFile.mockResolvedValue(null)
    mockReadFileAsBase64.mockResolvedValue(null)
    mockOpenPath.mockResolvedValue(true)
    mockApiPatchSettings.mockResolvedValue({})
    mockPatchTemplate.mockResolvedValue({})
    mockSetTemplate.mockResolvedValue({})
    mockDeleteTemplate.mockResolvedValue({})
    mockSetOutputResolution.mockResolvedValue({})
    mockSetBackgroundPath.mockResolvedValue({})
    mockSetLogoPath.mockResolvedValue({})
    mockStartPipelineExport.mockResolvedValue({})
    mockStopExport.mockResolvedValue({})
    mockUseProgressRowsQuery.mockReturnValue({
      data: {
        rows: [
          {
            batch: 'Batch 1',
            run_date: '2026-06-29',
            channel: 'Primary',
            status: 'queued',
            music: 'Ready',
            image: 'Ready',
            converter: 'Long Ready · Reel Ready',
            merge: 'Pending API parity',
            youtube: 'Pending',
            stage: 'Converter',
            notes: '',
            updated: '2026-06-29 10:00:00',
            meta: {
              batch_id: 'batch-1',
              profile_id: 'profile-1',
              role: 'ok',
              run_dir: 'D:/MusicGenerator/runs/batch-1/ok',
              source_mode: 'manual',
              background_16x9_path: 'D:/MusicGenerator/runs/batch-1/ok/background-16x9.png',
              background_9x16_path: 'D:/MusicGenerator/runs/batch-1/ok/background-9x16.png',
              thumbnail_16x9_path: 'D:/MusicGenerator/runs/batch-1/ok/thumbnail-16x9.png',
              thumbnail_9x16_path: 'D:/MusicGenerator/runs/batch-1/ok/thumbnail-9x16.png',
              long_ready: true,
              reel_ready: true,
              expected: 1,
              saved: 1,
              bg_ready: 1,
              bg_total: 1,
              th_ready: 1,
              th_total: 1,
              bg_status: 'success',
              th_status: 'success',
              youtube_status: 'pending',
              youtube_url: null,
              youtube_success: 0,
              youtube_pending: 0,
              youtube_failed: 0,
              music_started_at: null,
              music_updated_at: null,
              image_started_at: null,
              image_updated_at: null,
              youtube_created_at: null,
              youtube_updated_at: null,
            },
          },
        ],
        summary: 'Ready',
        updated_at: '2026-06-29 10:00:00',
      },
      isLoading: false,
      isError: false,
      isFetching: false,
      refetch: vi.fn(),
    })
    mockUseVideoWorkspaceQuery.mockReturnValue({
      data: {
        template: {
          templateName: 'Bass Drive',
          style: 'liquid',
          spectrumEnabled: true,
          layers: [{ id: 'layer-1' }, { id: 'layer-2' }],
          textOverlays: [],
          audioSettings: {
            sensitivity: 1.31,
            smoothing: 0.8,
          },
          position: {
            anchor: 'center',
            x: 0,
            y: 0,
          },
          backgroundSettings: {
            fitMode: 'cover',
            userScale: 1,
            brightness: 1.25,
            reactivity: 2,
            smoothing: 0.35,
            motionMode: 'zoom',
            motionZoomStrength: 1,
            motionVibrateStrength: 1,
          },
          effects: {
            vignette: {
              enabled: false,
              strength: 0.35,
              feather: 0.65,
              opacity: 0.65,
              color: '#000000',
            },
            smoke: {
              enabled: false,
              strength: 0.35,
              blur: 0.55,
              noise: 0.55,
              speed: 0.35,
              opacity: 0.55,
              color: '#000000',
            },
          },
          logoSettings: {
            enabled: true,
            spinEnabled: false,
            spinDirection: 'cw',
            spinSpeed: 0,
            circleMask: true,
            size: 200,
            opacity: 1,
            reactivity: 0.7,
            smoothing: 0.59,
          },
          particlesSettings: {
            enabled: true,
            maxCount: 1200,
            spawnRate: 400,
            lifetimeSec: 3.75,
            speed: 10.9,
            reactivity: 0.5,
            smoothing: 0.65,
            spawnMode: 'reactiveOnly',
            spawnTrigger: 'both',
            spawnThreshold: 0.15,
            variant: 'classic',
            spawnArea: 'centerRing',
            sizeJitter: 0,
            drift: 0,
            swirl: 0,
            style: 'dot',
            size: 2.5,
            opacity: 1,
            color: '#ffffff',
            reactColor: '#ffffff',
            reactStrength: 0.65,
          },
        },
        templateId: 'template-1',
        templateName: 'Bass Drive',
        templates: [
          {
            id: 'template-1',
            name: 'Bass Drive',
            kind: 'user',
            updatedAt: '2026-06-15 18:05:32',
          },
        ],
        outputResolution: '1920x1080',
        previewAspectRatio: {
          width: 1920,
          height: 1080,
        },
        backgroundPath: 'D:/MusicGenerator/backgrounds/bg.png',
        logoPath: 'D:/MusicGenerator/logos/logo.png',
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
          currentStatus: 'Read-only bootstrap loaded from local Python template/settings sources.',
          outputDir: 'D:/MusicGenerator/videos',
          currentOutputPath: null,
          totalJobs: 0,
          completedJobs: 0,
          lastOutputPath: null,
          lastMergedOutputPath: null,
        },
        ui: {
          previewTitle: 'Preview: Bass Drive',
          livePreviewOpen: false,
          source: 'python-local',
          notes: ['This first Electron bridge loads local Python template/state sources only.'],
        },
      },
      isLoading: false,
      isError: false,
      isFetching: false,
      refetch: vi.fn(),
    })
  })

  afterEach(() => {
    vi.clearAllMocks()
    window.localStorage.clear()
    window.sessionStorage.clear()
  })

  it('renders the real video bridge bootstrap shell', () => {
    renderPage()

    expect(screen.getByText(/video controls/i)).toBeInTheDocument()
    expect(screen.getByText(/diagnostics & recovery/i)).toBeInTheDocument()
    expect(screen.getAllByText(/renderer preview/i).length).toBeGreaterThan(0)
    expect(screen.getByRole('heading', { name: /^inspector$/i })).toBeInTheDocument()
    expect(screen.getByText(/no text layer is selected yet/i)).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /^spectrum$/i }).length).toBeGreaterThan(0)
    expect(screen.getAllByRole('button', { name: /^background$/i }).length).toBeGreaterThan(0)
    expect(screen.getAllByRole('button', { name: /^logo$/i }).length).toBeGreaterThan(0)
    expect(screen.getAllByRole('button', { name: /^particles$/i }).length).toBeGreaterThan(0)
    expect(screen.queryAllByRole('button', { name: /^layer$/i }).length).toBe(0)
    expect(screen.getAllByText(/bass drive/i).length).toBeGreaterThan(0)
    expect(screen.getByRole('button', { name: /export queue/i })).toBeInTheDocument()
    expect(screen.getByText(/color style/i)).toBeInTheDocument()
    expect(screen.getAllByText(/solid color/i).length).toBeGreaterThan(0)
  })

  it('adds a text overlay through the extracted text editor flow', async () => {
    renderPage()

    const addButtons = screen.getAllByRole('button', { name: /^add$/i })
    fireEvent.click(addButtons[addButtons.length - 1])

    expect(screen.getByText(/selected 1\/1/i)).toBeInTheDocument()
    expect(screen.getByDisplayValue('')).toBeInTheDocument()
    expect(mockPatchTemplate).not.toHaveBeenCalled()

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /^save$/i })).toBeEnabled()
    })

    fireEvent.click(screen.getByRole('button', { name: /^save$/i }))

    await waitFor(() => {
      expect(mockPatchTemplate).toHaveBeenCalledWith(
        expect.objectContaining({
          textOverlays: [
            expect.objectContaining({
              text: '',
              anchor: 'center',
              sizePx: 46,
              animation: 'fade',
            }),
          ],
        }),
      )
    })
  })

  it('switches the right rail to the extracted export inspector', () => {
    renderPage()

    fireEvent.click(screen.getByRole('button', { name: /export queue/i }))

    expect(screen.getByText(/^track list$/i)).toBeInTheDocument()
    expect(screen.getByText(/^actions$/i)).toBeInTheDocument()
    expect(screen.getByText(/^status$/i)).toBeInTheDocument()
  })

  it('shows export progress percent and ETA in the export inspector', () => {
    const baseWorkspace = mockUseVideoWorkspaceQuery()
    mockUseVideoWorkspaceQuery.mockReturnValue({
      data: {
        ...baseWorkspace.data,
        export: {
          ...baseWorkspace.data.export,
          running: true,
          outputDir: 'F:/BassDrive/2026-06-01',
          currentOutputPath: "F:/BassDrive/2026-06-01/10. Don't let the retro blue-hour fade_OK_WEBGPU_20260706-221500.mp4",
          totalJobs: 240,
          completedJobs: 96,
          progressPercent: 40,
          estimatedRemainingSec: 125,
          currentStatus: 'Streaming manual WebGPU frames 96/240…',
        },
      },
      isLoading: false,
      isError: false,
      isFetching: false,
      refetch: vi.fn(),
    })

    renderPage()
    fireEvent.click(screen.getByRole('button', { name: /export queue/i }))

    expect(screen.getByText('96/240 · 40%')).toBeInTheDocument()
    expect(screen.getByText('Progress 40%')).toBeInTheDocument()
    expect(screen.getByText('ETA 2m 5s')).toBeInTheDocument()
    expect(screen.getByText(/Target output:/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /open output folder/i })).toBeEnabled()
    expect(screen.getByRole('button', { name: /open output file/i })).toBeEnabled()
  })

  it('uses the selected pipeline background when no manual preview background is set', () => {
    const baseWorkspace = mockUseVideoWorkspaceQuery()
    mockUseVideoWorkspaceQuery.mockReturnValue({
      data: {
        ...baseWorkspace.data,
        backgroundPath: '',
      },
      isLoading: false,
      isError: false,
      isFetching: false,
      refetch: vi.fn(),
    })

    renderPage()

    expect(screen.getByText('background-16x9.png')).toBeInTheDocument()
    expect(screen.getByText(/selected pipeline branch background/i)).toBeInTheDocument()
  })

  it('saves template name changes through the template patch bridge', async () => {
    renderPage()

    const templateNameInput = screen.getByDisplayValue('Bass Drive')
    fireEvent.change(templateNameInput, { target: { value: 'Boss Preview Template' } })
    expect(mockPatchTemplate).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: /^save$/i }))

    await waitFor(() => {
      expect(mockPatchTemplate).toHaveBeenCalledWith(
        expect.objectContaining({
          templateName: 'Boss Preview Template',
        }),
      )
    })
  })

  it('deletes the selected template through the desktop bridge after confirmation', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    renderPage()

    fireEvent.click(screen.getByRole('button', { name: /delete selected template/i }))

    await waitFor(() => {
      expect(mockDeleteTemplate).toHaveBeenCalledWith('template-1')
    })
  })

  it('keeps the selected background visible after a workspace refresh', async () => {
    const selectedBackgroundPath = 'D:/MusicGenerator/backgrounds/custom-preview.png'
    mockSelectFile.mockResolvedValue(selectedBackgroundPath)

    const baseData = {
      template: {
        templateName: 'Bass Drive',
        style: 'liquid',
        spectrumEnabled: true,
        layers: [{ id: 'layer-1' }, { id: 'layer-2' }],
        textOverlays: [],
        audioSettings: {
          sensitivity: 1.31,
          smoothing: 0.8,
        },
        position: {
          anchor: 'center',
          x: 0,
          y: 0,
        },
        backgroundSettings: {
          fitMode: 'cover',
          userScale: 1,
          brightness: 1.25,
          reactivity: 2,
          smoothing: 0.35,
          motionMode: 'zoom',
          motionZoomStrength: 1,
          motionVibrateStrength: 1,
        },
        effects: {
          vignette: {
            enabled: false,
            strength: 0.35,
            feather: 0.65,
            opacity: 0.65,
            color: '#000000',
          },
          smoke: {
            enabled: false,
            strength: 0.35,
            blur: 0.55,
            noise: 0.55,
            speed: 0.35,
            opacity: 0.55,
            color: '#000000',
          },
        },
        logoSettings: {
          enabled: true,
          spinEnabled: false,
          spinDirection: 'cw',
          spinSpeed: 0,
          circleMask: true,
          size: 200,
          opacity: 1,
          reactivity: 0.7,
          smoothing: 0.59,
        },
        particlesSettings: {
          enabled: true,
          maxCount: 1200,
          spawnRate: 400,
          lifetimeSec: 3.75,
          speed: 10.9,
          reactivity: 0.5,
          smoothing: 0.65,
          spawnMode: 'reactiveOnly',
          spawnTrigger: 'both',
          spawnThreshold: 0.15,
          variant: 'classic',
          spawnArea: 'centerRing',
          sizeJitter: 0,
          drift: 0,
          swirl: 0,
          style: 'dot',
          size: 2.5,
          opacity: 1,
          color: '#ffffff',
          reactColor: '#ffffff',
          reactStrength: 0.65,
        },
      },
      templateId: 'template-1',
      templateName: 'Bass Drive',
      templates: [
        {
          id: 'template-1',
          name: 'Bass Drive',
          kind: 'user',
          updatedAt: '2026-06-15 18:05:32',
        },
      ],
      outputResolution: '1920x1080',
      previewAspectRatio: {
        width: 1920,
        height: 1080,
      },
      backgroundPath: 'D:/MusicGenerator/backgrounds/bg.png',
      logoPath: 'D:/MusicGenerator/logos/logo.png',
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
        currentStatus: 'Read-only bootstrap loaded from local Python template/settings sources.',
        outputDir: 'D:/MusicGenerator/videos',
        totalJobs: 0,
        completedJobs: 0,
        lastOutputPath: null,
        lastMergedOutputPath: null,
      },
      ui: {
        previewTitle: 'Preview: Bass Drive',
        livePreviewOpen: false,
        source: 'python-local' as const,
        notes: ['This first Electron bridge loads local Python template/state sources only.'],
      },
    }

    mockUseVideoWorkspaceQuery.mockReturnValue({
      data: baseData,
      isLoading: false,
      isError: false,
      isFetching: false,
      refetch: vi.fn(),
    })

    const view = renderPage()

    const backgroundButtons = screen.getAllByRole('button', { name: /^background$/i })
    fireEvent.click(backgroundButtons[backgroundButtons.length - 1])

    await waitFor(() => {
      expect(mockApiPatchSettings).toHaveBeenCalledWith({
        videoRenderBackgroundPath: selectedBackgroundPath,
      })
    })

    await waitFor(() => {
      expect(screen.getByText('custom-preview.png')).toBeInTheDocument()
    })

    mockUseVideoWorkspaceQuery.mockReturnValue({
      data: {
        ...baseData,
        template: {
          ...baseData.template,
          style: 'stacked',
        },
        backgroundPath: '',
      },
      isLoading: false,
      isError: false,
      isFetching: false,
      refetch: vi.fn(),
    })

    view.rerender(
      <QueryClientProvider
        client={
          new QueryClient({
            defaultOptions: {
              queries: {
                gcTime: Infinity,
                retry: false,
              },
            },
          })
        }
      >
        <VideoWorkspacePage />
      </QueryClientProvider>,
    )

    await waitFor(() => {
      expect(screen.getByText('custom-preview.png')).toBeInTheDocument()
    })
  })

  it('preserves the local spectrum preset during same-template workspace refreshes and only saves on explicit action', async () => {
    const baseWorkspace = mockUseVideoWorkspaceQuery()
    mockUseVideoWorkspaceQuery.mockReturnValue({
      data: {
        ...baseWorkspace.data,
        template: {
          ...baseWorkspace.data.template,
          style: 'liquid',
        },
      },
      isLoading: false,
      isError: false,
      isFetching: false,
      refetch: vi.fn(),
    })

    const view = renderPage()

    const presetTrigger = screen
      .getAllByRole('combobox')
      .find((element) => element.textContent?.match(/liquid mass/i))

    expect(presetTrigger).toBeTruthy()
    if (!presetTrigger) {
      throw new Error('Spectrum preset trigger not found')
    }
    fireEvent.click(presetTrigger)
    fireEvent.click(await screen.findByText('Straight Bars'))

    expect(mockPatchTemplate).not.toHaveBeenCalled()

    mockUseVideoWorkspaceQuery.mockReturnValue({
      data: {
        ...baseWorkspace.data,
        template: {
          ...baseWorkspace.data.template,
          style: 'liquid',
        },
      },
      isLoading: false,
      isError: false,
      isFetching: false,
      refetch: vi.fn(),
    })

    view.rerender(
      <QueryClientProvider
        client={
          new QueryClient({
            defaultOptions: {
              queries: {
                gcTime: Infinity,
                retry: false,
              },
            },
          })
        }
      >
        <VideoWorkspacePage />
      </QueryClientProvider>,
    )

    await waitFor(() => {
      expect(screen.getAllByRole('combobox').some((element) => element.textContent?.match(/straight bars/i))).toBe(true)
    })

    fireEvent.click(screen.getByRole('button', { name: /^save$/i }))

    await waitFor(() => {
      expect(mockPatchTemplate).toHaveBeenCalledWith(
        expect.objectContaining({
          style: 'straight-bars',
        }),
      )
    })
  })

  it('updates preview draft props immediately while editing spectrum, background, logo, particles, and text', async () => {
    renderPage()

    await activateWorkspaceTab(/^spectrum$/i, /one curated preset selector/i)
    fireEvent.change(screen.getByLabelText('Motion Smoothing'), { target: { value: '33' } })
    expect(mockPatchTemplate).not.toHaveBeenCalled()

    await activateWorkspaceTab(/^background$/i, /reset transform/i)
    fireEvent.change(screen.getByLabelText('Brightness'), { target: { value: '1.60' } })
    expect(mockPatchTemplate).not.toHaveBeenCalled()

    await activateWorkspaceTab(/^logo$/i, /select logo/i)
    fireEvent.change(screen.getByLabelText('Opacity'), { target: { value: '0.42' } })
    expect(mockPatchTemplate).not.toHaveBeenCalled()

    await activateWorkspaceTab(/^particles$/i, /spawn mode/i)
    fireEvent.change(screen.getByLabelText('Opacity'), { target: { value: '0.47' } })
    expect(mockPatchTemplate).not.toHaveBeenCalled()

    const addButtons = screen.getAllByRole('button', { name: /^add$/i })
    fireEvent.click(addButtons[addButtons.length - 1])

    await waitFor(() => expect(screen.getByText(/editing text 1/i)).toBeInTheDocument())
    expect(mockPatchTemplate).not.toHaveBeenCalled()

    fireEvent.change(screen.getByDisplayValue(''), { target: { value: 'Lead Title' } })

    expect(screen.getByDisplayValue('Lead Title')).toBeInTheDocument()
    expect(mockPatchTemplate).not.toHaveBeenCalled()
  })
})
