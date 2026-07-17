import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'

import { SettingsWorkspacePage } from '@/features/settings/SettingsWorkspacePage'

const mockUseSettingsWorkspaceQuery = vi.fn()
const mockApiCreateUserProfile = vi.fn()
const mockApiDeleteUserProfile = vi.fn()
const mockApiUpdateUserProfile = vi.fn()
const mockApiPatchSettings = vi.fn()
const mockApiGetContentPoolStats = vi.fn()
const mockApiListContentPoolItems = vi.fn()
const mockApiStartYouTubeConnection = vi.fn()
const mockApiSelectYouTubeChannel = vi.fn()
const mockApiDisconnectYouTubeConnection = vi.fn()
const mockApiListImageSamplePacks = vi.fn()
const mockOpenExternalUrl = vi.fn()
const mockSelectPath = vi.fn()
const mockOpenPath = vi.fn()
const mockListDirectoryImages = vi.fn()
const mockReadFileAsBase64 = vi.fn()
const mockDownloadAndExtractZip = vi.fn()
const mockDesktopApi = {
  files: {
    openExternalUrl: (...args: unknown[]) => mockOpenExternalUrl(...args),
    selectFile: vi.fn(),
    selectPath: (...args: unknown[]) => mockSelectPath(...args),
    openPath: (...args: unknown[]) => mockOpenPath(...args),
    listDirectoryImages: (...args: unknown[]) => mockListDirectoryImages(...args),
    readFileAsBase64: (...args: unknown[]) => mockReadFileAsBase64(...args),
    downloadAndExtractZip: (...args: unknown[]) => mockDownloadAndExtractZip(...args),
  },
}

vi.mock('@/features/settings/useSettingsWorkspaceQuery', () => ({
  useSettingsWorkspaceQuery: () => mockUseSettingsWorkspaceQuery(),
}))

vi.mock('@/shared/api/desktop', () => ({
  getDesktopApi: () => mockDesktopApi,
}))

vi.mock('@/shared/api/platformEndpoints', async () => {
  const actual = await vi.importActual<typeof import('@/shared/api/platformEndpoints')>(
    '@/shared/api/platformEndpoints',
  )

  return {
    ...actual,
    apiCreateUserProfile: (...args: Parameters<typeof actual.apiCreateUserProfile>) => mockApiCreateUserProfile(...args),
    apiDeleteUserProfile: (...args: Parameters<typeof actual.apiDeleteUserProfile>) => mockApiDeleteUserProfile(...args),
    apiUpdateUserProfile: (...args: Parameters<typeof actual.apiUpdateUserProfile>) => mockApiUpdateUserProfile(...args),
    apiPatchSettings: (...args: Parameters<typeof actual.apiPatchSettings>) => mockApiPatchSettings(...args),
    apiGetContentPoolStats: (...args: Parameters<typeof actual.apiGetContentPoolStats>) => mockApiGetContentPoolStats(...args),
    apiListContentPoolItems: (...args: Parameters<typeof actual.apiListContentPoolItems>) => mockApiListContentPoolItems(...args),
    apiListImageSamplePacks: (...args: Parameters<typeof actual.apiListImageSamplePacks>) => mockApiListImageSamplePacks(...args),
    apiStartYouTubeConnection: (...args: Parameters<typeof actual.apiStartYouTubeConnection>) =>
      mockApiStartYouTubeConnection(...args),
    apiSelectYouTubeChannel: (...args: Parameters<typeof actual.apiSelectYouTubeChannel>) =>
      mockApiSelectYouTubeChannel(...args),
    apiDisconnectYouTubeConnection: (...args: Parameters<typeof actual.apiDisconnectYouTubeConnection>) =>
      mockApiDisconnectYouTubeConnection(...args),
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
    <MemoryRouter>
      <QueryClientProvider client={queryClient}>
        <SettingsWorkspacePage />
      </QueryClientProvider>
    </MemoryRouter>,
  )
}

function buildWorkspaceData() {
  return {
    me: {
      id: 'user-1',
      email: 'boss@example.com',
      email_confirmed: true,
      display_name: 'Boss',
      credit_balance: 100,
      plan_name: 'Pro',
      profile_allowance: 5,
      channel_profile_count: 2,
    },
    appMeta: {
      name: 'CAMXORA',
      version: '1.0.0',
      isDev: true,
      platform: 'win32',
    },
    apiBaseUrl: 'http://localhost:8000/api/v1',
    isApiBaseUrlOverridden: false,
    videoWorkspace: {
      template: {},
      templateId: 'template-1',
      templateName: 'Main Template',
      templates: [
        {
          id: 'template-1',
          name: 'Main Template',
          kind: 'local',
          updatedAt: '2026-06-25 10:00:00',
        },
        {
          id: 'reel-1',
          name: 'Reel Template',
          kind: 'local',
          updatedAt: '2026-06-25 10:00:00',
        },
      ],
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
        workers: 1,
        autoMerge: false,
        currentStatus: 'Ready',
        outputDir: null,
      },
      ui: {
        previewTitle: 'Preview: Main Template',
        livePreviewOpen: false,
        source: 'python-local',
        notes: [],
      },
    },
    settings: {
      ffmpegPath: 'C:/ffmpeg/bin/ffmpeg.exe',
      downloadsDir: 'D:/MusicGenerator/downloads',
      sunoOutputDir: 'D:/MusicGenerator/suno',
      mergedDir: 'D:/MusicGenerator/merged',
      perfMusicWorkers: 1,
      perfImageWorkers: 4,
      perfExportWorkers: 2,
      perfMergeWorkers: 1,
      perfYouTubeWorkers: 1,
      youtubeUploadChunkSizeMb: 256,
      imageBackgroundSamplesDir: 'D:/MusicGenerator/background-samples',
      imageThumbnailSamplesDir: 'D:/MusicGenerator/thumb-samples',
      imageBgRandom: false,
      imageThumbRandom: true,
      imageBgSamples: ['D:/MusicGenerator/background-samples/bg-selected.png'],
      imageThumbSamples: [],
      imageOutputDir: 'D:/MusicGenerator/image-output',
      outputResolution: '1920x1080',
      styleStrength: 60,
      backgroundSourceMode: 'samples',
      thumbnailOverlayMode: 'ai',
      sunoCallbackUrl: 'https://example.ngrok.app/callback',
      sunoTimeoutMs: 90000,
      sunoRetryCount: 3,
      sunoDefaultVersion: 'v5.5',
      sunoMergeEnabled: false,
      sunoMergeGroupSize: 0,
      sunoCreditsReserve: 10,
      sunoCreditsCostMusic: 5,
      sunoCreditsCostLyrics: 1,
    },
    profiles: [
      {
        id: 'profile-1',
        user_id: 'user-1',
        name: 'Boss Primary',
        folder_name: 'boss-primary',
        run_prefix: 'boss',
        logo_path: 'D:/MusicGenerator/logos/logo.png',
        video_template_id: 'template-1',
        reel_template_id: 'reel-1',
        output_resolution: '1920x1080',
        image_config: {},
        youtube_config: {},
      },
      {
        id: 'profile-2',
        user_id: 'user-1',
        name: 'Night Drive',
        folder_name: 'electro-drive',
        run_prefix: 'ndrive',
        logo_path: '',
        video_template_id: 'template-1',
        reel_template_id: 'reel-1',
        output_resolution: '1080x1080',
        image_config: {},
        youtube_config: {},
      },
    ],
    descriptionOptions: [
      {
        id: 'description-1',
        name: 'EDM / Workout Gym',
      },
      {
        id: 'description-2',
        name: 'Dark Phonk Trap',
      },
    ],
    structureOptions: [
      {
        id: 'structure-1',
        name: 'Festival Big Drop',
      },
      {
        id: 'structure-2',
        name: 'Tech House',
      },
    ],
    youtubeConnections: [],
  }
}

describe('SettingsWorkspacePage', () => {
  beforeEach(() => {
    const data = buildWorkspaceData()
    mockApiCreateUserProfile.mockResolvedValue({
      id: 'profile-3',
      user_id: 'user-1',
      name: 'Morning Glow',
      folder_name: 'morning-glow',
      run_prefix: 'mglow',
      logo_path: '',
      video_template_id: 'template-1',
      reel_template_id: 'reel-1',
      output_resolution: '1920x1080',
      image_config: {},
      youtube_config: {},
    })
    mockApiDeleteUserProfile.mockResolvedValue({ message: 'Deleted the selected profile.' })
    mockApiUpdateUserProfile.mockImplementation(async (profileId: string, payload: Record<string, unknown>) => ({
      id: profileId,
      user_id: 'user-1',
      name: 'Boss Primary',
      folder_name: 'boss-primary',
      run_prefix: 'boss',
      logo_path: 'D:/MusicGenerator/logos/logo.png',
      video_template_id: 'template-1',
      reel_template_id: 'reel-1',
      output_resolution: '1920x1080',
      image_config: {},
      youtube_config: payload.youtube_config ?? {},
    }))
    mockApiPatchSettings.mockResolvedValue({})
    mockApiGetContentPoolStats.mockResolvedValue({
      openings: { total: 64, unused: 28 },
      titles: { total: 120, unused: 75 },
      albums: { total: 80, unused: 33 },
    })
    mockApiListContentPoolItems.mockImplementation(async (kind: string) => {
      if (kind === 'openings') {
        return {
          kind,
          total: 64,
          limit: 100,
          offset: 0,
          items: [
            {
              id: 3,
              text: 'Drive through the dark',
              secondary_text: 'Chasing every light',
              used_count: 7,
              created_at: '2026-06-25T08:00:00Z',
            },
          ],
        }
      }
      return {
        kind,
        total: kind === 'titles' ? 120 : 80,
        limit: 100,
        offset: 0,
        items: [
          {
            id: 8,
            text: kind === 'titles' ? 'Midnight Echo' : 'Neon Afterglow',
            secondary_text: null,
            used_count: kind === 'titles' ? 5 : 2,
            created_at: '2026-06-27T10:00:00Z',
          },
        ],
      }
    })
    mockApiStartYouTubeConnection.mockResolvedValue({
      session_id: 'session-1',
      auth_url: 'https://accounts.google.com/o/oauth2/auth',
      status: 'pending_browser',
    })
    mockApiSelectYouTubeChannel.mockResolvedValue({
      profile_id: 'profile-1',
      profile_name: 'Boss Primary',
      status: 'connected',
      channel_id: 'channel-1',
      channel_title: 'Boss Official',
      session_id: 'session-1',
      channels: [],
      message: 'Channel connected.',
    })
    mockApiDisconnectYouTubeConnection.mockResolvedValue({ message: 'YouTube channel disconnected.' })
    mockApiListImageSamplePacks.mockResolvedValue({ items: [] })
    mockOpenExternalUrl.mockResolvedValue(true)
    mockOpenPath.mockResolvedValue(true)
    mockSelectPath.mockResolvedValue(null)
    mockDownloadAndExtractZip.mockResolvedValue({ ok: true, installedCount: 0 })
    mockListDirectoryImages.mockImplementation(async ({ directoryPath }: { directoryPath: string }) => {
      if (String(directoryPath).includes('background-samples')) {
        return [
          'D:/MusicGenerator/background-samples/bg-selected.png',
          'D:/MusicGenerator/background-samples/bg-other.png',
        ]
      }
      return [
        'D:/MusicGenerator/thumb-samples/thumb-1.png',
        'D:/MusicGenerator/thumb-samples/thumb-2.png',
      ]
    })
    mockReadFileAsBase64.mockResolvedValue('ZmFrZQ==')
    mockUseSettingsWorkspaceQuery.mockReturnValue({
      data,
      isLoading: false,
      isError: false,
      isFetching: false,
      refetch: vi.fn(),
    })
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('renders the compact Python-style tab workspace', () => {
    renderPage()

    expect(screen.getByRole('button', { name: /youtube/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /profiles/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /publication/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /preferences/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /database/i })).not.toBeInTheDocument()
    expect(screen.queryByText(/python primary settings workspace/i)).not.toBeInTheDocument()
    expect(screen.getByText(/your profiles/i)).toBeInTheDocument()
    expect(screen.getByText(/source: account profile/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /save all changes/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^refresh$/i })).not.toBeInTheDocument()
  })

  it('searches profiles by folder name and run prefix like the Python tab', () => {
    renderPage()

    fireEvent.change(screen.getByPlaceholderText(/search by name, folder, or prefix/i), {
      target: { value: 'electro-drive' },
    })

    expect(screen.getAllByText(/night drive/i).length).toBeGreaterThan(0)
    expect(screen.queryByRole('button', { name: /boss primary/i })).not.toBeInTheDocument()
  })

  it('creates a new profile inline from the Settings profiles tab', async () => {
    renderPage()

    fireEvent.click(screen.getByRole('button', { name: /add new profile/i }))

    expect(screen.getByText(/creating a new inline profile draft/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /create profile/i })).toBeInTheDocument()

    const textboxes = screen.getAllByRole('textbox')

    fireEvent.change(textboxes[1], {
      target: { value: 'Morning Glow' },
    })
    fireEvent.change(textboxes[2], {
      target: { value: 'morning-glow' },
    })
    fireEvent.change(textboxes[3], {
      target: { value: 'mglow' },
    })

    fireEvent.click(screen.getByRole('button', { name: /create profile/i }))

    await waitFor(() => {
      expect(mockApiCreateUserProfile).toHaveBeenCalledWith(
        expect.objectContaining({
          name: 'Morning Glow',
          folder_name: 'morning-glow',
          run_prefix: 'mglow',
        }),
      )
    })
  })

  it('keeps the inline draft editable when there are no existing profiles', async () => {
    const data = buildWorkspaceData()
    mockUseSettingsWorkspaceQuery.mockReturnValue({
      data: {
        ...data,
        me: {
          ...data.me,
          profile_allowance: 2,
          channel_profile_count: 0,
        },
        profiles: [],
        youtubeConnections: [],
      },
      isLoading: false,
      isError: false,
      isFetching: false,
      refetch: vi.fn(),
    })

    renderPage()

    expect(screen.getByText(/no profiles yet\. click add new profile to create your first profile\./i)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /add new profile/i }))

    const nameInput = screen.getAllByRole('textbox')[1] as HTMLInputElement
    expect(nameInput).toBeEnabled()

    fireEvent.change(nameInput, {
      target: { value: 'Morning Glow' },
    })

    expect(screen.getByDisplayValue('Morning Glow')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /create profile/i })).toBeInTheDocument()
  })

  it('saves the python settings tab fields through the global footer save action', async () => {
    renderPage()

    fireEvent.click(screen.getByRole('button', { name: /^preferences$/i }))
    fireEvent.change(screen.getByDisplayValue('C:/ffmpeg/bin/ffmpeg.exe'), {
      target: { value: 'D:/Tools/ffmpeg.exe' },
    })
    fireEvent.click(screen.getByRole('button', { name: /^profiles$/i }))
    fireEvent.click(screen.getByRole('button', { name: /save all changes/i }))

    await waitFor(() => {
      expect(mockApiPatchSettings).toHaveBeenCalledWith(
        expect.objectContaining({
          ffmpegPath: 'D:/Tools/ffmpeg.exe',
        }),
      )
    })
  })

  it('writes export workers to both electron and python runtime keys when preferences are saved', async () => {
    renderPage()

    fireEvent.click(screen.getByRole('button', { name: /^preferences$/i }))

    const exportCard = screen.getByText(/export workers/i).closest('div.rounded-xl')
    const exportButtons = exportCard?.querySelectorAll('button')
    expect(exportButtons?.length).toBeGreaterThanOrEqual(2)
    fireEvent.click(exportButtons?.[1] as Element)
    fireEvent.click(screen.getByRole('button', { name: /^profiles$/i }))
    fireEvent.click(screen.getByRole('button', { name: /save all changes/i }))

    await waitFor(() => {
      expect(mockApiPatchSettings).toHaveBeenCalledWith(
        expect.objectContaining({
          perfExportWorkers: 3,
          videoExportWorkers: 3,
        }),
      )
    })
  })

  it('renders sample curation controls from Preferences instead of the Image page', async () => {
    renderPage()

    fireEvent.click(screen.getByRole('button', { name: /^preferences$/i }))

    expect(await screen.findByText('Sample Library Manager')).toBeInTheDocument()
    expect(screen.getByText('Background Samples')).toBeInTheDocument()
    expect(screen.getByText('Thumbnail Samples')).toBeInTheDocument()
    expect(screen.getByText(/selected 1\/5/i)).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: /bg-selected\.png/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /thumb-1\.png/i })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: /^image$/i })).not.toBeInTheDocument()
  })

  it('renders the descriptions table and editor layout', () => {
    renderPage()

    fireEvent.click(screen.getByRole('button', { name: /descriptions/i }))

    expect(screen.getByText(/music description names/i)).toBeInTheDocument()
    expect(screen.getByText(/available structures/i)).toBeInTheDocument()
    expect(screen.getAllByText(/edm \/ workout gym/i).length).toBeGreaterThan(0)
    expect(screen.getByText(/content is intentionally hidden here/i)).toBeInTheDocument()
  })

  it('lets publication switch profiles through a dropdown', () => {
    renderPage()

    fireEvent.click(screen.getByRole('button', { name: /publication/i }))

    expect(screen.getAllByText(/boss primary/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/^music$/i).length).toBeGreaterThan(0)
  })

  it('renders python-style scheduled helper text and no native datetime field in publication', () => {
    const data = buildWorkspaceData()
    mockUseSettingsWorkspaceQuery.mockReturnValue({
      data: {
        ...data,
        profiles: data.profiles.map((profile) =>
          profile.id === 'profile-1'
            ? {
                ...profile,
                youtube_config: {
                  visibility: 'scheduled',
                  publish_at: '2026-07-01T09:30:00',
                },
              }
            : profile,
        ),
      },
      isLoading: false,
      isError: false,
      isFetching: false,
      refetch: vi.fn(),
    })

    const { container } = renderPage()

    fireEvent.click(screen.getByRole('button', { name: /publication/i }))

    expect(screen.getByText(/scheduled uploads use the batch date/i)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /jul 1, 2026/i })).not.toBeInTheDocument()
    expect(container.querySelector('input[type="datetime-local"]')).toBeNull()
  })

  it('saves scheduled publication defaults using python-style hh:mm payloads', async () => {
    const data = buildWorkspaceData()
    mockUseSettingsWorkspaceQuery.mockReturnValue({
      data: {
        ...data,
        profiles: data.profiles.map((profile) =>
          profile.id === 'profile-1'
            ? {
                ...profile,
                youtube_config: {
                  visibility: 'scheduled',
                  publish_at: '2026-07-01T09:30:00',
                },
              }
            : profile,
        ),
      },
      isLoading: false,
      isError: false,
      isFetching: false,
      refetch: vi.fn(),
    })

    renderPage()

    fireEvent.click(screen.getByRole('button', { name: /publication/i }))
    fireEvent.change(screen.getAllByRole('textbox')[0], {
      target: { value: 'Updated scheduled description' },
    })
    fireEvent.click(screen.getByRole('button', { name: /save publication/i }))

    await waitFor(() => {
      expect(mockApiUpdateUserProfile).toHaveBeenCalledWith(
        'profile-1',
        expect.objectContaining({
          youtube_config: expect.objectContaining({
            visibility: 'scheduled',
            publish_at: '09:30',
          }),
        }),
      )
    })
  })

  it('starts the youtube browser connect flow for the selected profile', async () => {
    renderPage()

    fireEvent.click(screen.getByRole('button', { name: /^youtube$/i }))
    fireEvent.click(screen.getByRole('button', { name: /connect channel/i }))

    await waitFor(() => {
      expect(mockApiStartYouTubeConnection).toHaveBeenCalledWith('profile-1')
      expect(mockOpenExternalUrl).toHaveBeenCalledWith('https://accounts.google.com/o/oauth2/auth')
    })
  })

  it('shows the live youtube connection status in the profiles summary instead of inferring from publication config', () => {
    const data = buildWorkspaceData()
    mockUseSettingsWorkspaceQuery.mockReturnValue({
      data: {
        ...data,
        youtubeConnections: [
          {
            profile_id: 'profile-1',
            profile_name: 'Boss Primary',
            status: 'pending_browser',
            channel_id: null,
            channel_title: null,
            session_id: 'session-1',
            channels: [],
            message: 'Continue the Google sign-in flow in your browser.',
          },
        ],
      },
      isLoading: false,
      isError: false,
      isFetching: false,
      refetch: vi.fn(),
    })

    renderPage()

    expect(screen.getByText(/youtube: waiting for browser sign-in/i)).toBeInTheDocument()
  })

  it('allows restarting the youtube browser flow while waiting for browser sign-in', async () => {
    const data = buildWorkspaceData()
    mockUseSettingsWorkspaceQuery.mockReturnValue({
      data: {
        ...data,
        youtubeConnections: [
          {
            profile_id: 'profile-1',
            profile_name: 'Boss Primary',
            status: 'pending_browser',
            channel_id: null,
            channel_title: null,
            session_id: 'session-1',
            channels: [],
            message: 'Continue the Google sign-in flow in your browser.',
          },
        ],
      },
      isLoading: false,
      isError: false,
      isFetching: false,
      refetch: vi.fn(),
    })

    renderPage()

    fireEvent.click(screen.getByRole('button', { name: /^youtube$/i }))
    fireEvent.click(screen.getByRole('button', { name: /restart sign-in/i }))

    await waitFor(() => {
      expect(mockApiStartYouTubeConnection).toHaveBeenCalledWith('profile-1')
      expect(mockOpenExternalUrl).toHaveBeenCalledWith('https://accounts.google.com/o/oauth2/auth')
    })
  })

  it('uses the themed confirmation dialog before disconnecting youtube', async () => {
    const data = buildWorkspaceData()
    mockUseSettingsWorkspaceQuery.mockReturnValue({
      data: {
        ...data,
        youtubeConnections: [
          {
            profile_id: 'profile-1',
            profile_name: 'Boss Primary',
            status: 'connected',
            channel_id: 'channel-1',
            channel_title: 'Boss Official',
            session_id: null,
            channels: [],
            message: 'Channel connected.',
          },
        ],
      },
      isLoading: false,
      isError: false,
      isFetching: false,
      refetch: vi.fn(),
    })

    renderPage()

    fireEvent.click(screen.getByRole('button', { name: /^youtube$/i }))
    fireEvent.click(screen.getByRole('button', { name: /^disconnect$/i }))

    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByText(/disconnect youtube for "boss primary"\?/i)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /disconnect channel/i }))

    await waitFor(() => {
      expect(mockApiDisconnectYouTubeConnection).toHaveBeenCalledWith('profile-1')
    })
  })

  it('renders channel selection state and removes the stale publication oauth selector', () => {
    const data = buildWorkspaceData()
    mockUseSettingsWorkspaceQuery.mockReturnValue({
      data: {
        ...data,
        youtubeConnections: [
          {
            profile_id: 'profile-1',
            profile_name: 'Boss Primary',
            status: 'awaiting_channel_selection',
            channel_id: null,
            channel_title: null,
            session_id: 'session-1',
            channels: [
              { id: 'channel-1', title: 'Boss Official' },
              { id: 'channel-2', title: 'Boss Backup' },
            ],
            message: 'Select which returned YouTube channel to attach to this profile.',
          },
        ],
      },
      isLoading: false,
      isError: false,
      isFetching: false,
      refetch: vi.fn(),
    })

    renderPage()

    fireEvent.click(screen.getByRole('button', { name: /^youtube$/i }))
    expect(screen.getByRole('button', { name: /attach channel/i })).toBeInTheDocument()
    expect(screen.getAllByText(/boss official/i).length).toBeGreaterThan(0)

    fireEvent.click(screen.getByRole('button', { name: /publication/i }))
    expect(screen.queryByText(/youtube oauth app/i)).not.toBeInTheDocument()
    expect(screen.getByText(/channel access/i)).toBeInTheDocument()
  })

  it('renders structure names without loading content', () => {
    renderPage()

    fireEvent.click(screen.getByRole('button', { name: /structures/i }))

    expect(screen.getByText(/music structure names/i)).toBeInTheDocument()
    expect(screen.getAllByText(/festival big drop/i).length).toBeGreaterThan(0)
    expect(screen.getByText(/full structure content remains in the admin portal/i)).toBeInTheDocument()
  })

  it('renders read-only pool rows and used counts while keeping admin ownership', async () => {
    renderPage()

    fireEvent.click(screen.getByRole('button', { name: /pools/i }))

    await waitFor(() => {
      expect(screen.getByText(/drive through the dark \/ chasing every light/i)).toBeInTheDocument()
    })
    expect(screen.getAllByText(/^7$/).length).toBeGreaterThan(0)
    expect(screen.getByText(/all editing stays in the admin portal/i)).toBeInTheDocument()
  })

  it('saves the supported suno settings fields through the dedicated suno action', async () => {
    renderPage()

    fireEvent.click(screen.getByRole('button', { name: /suno/i }))
    expect(screen.queryByText(/callback url/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/credits reserve/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/music cost/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/lyrics cost/i)).not.toBeInTheDocument()
    fireEvent.change(screen.getByDisplayValue('3'), {
      target: { value: '4' },
    })
    fireEvent.click(screen.getByRole('button', { name: /save suno/i }))

    await waitFor(() => {
      expect(mockApiPatchSettings).toHaveBeenCalledWith(
        expect.objectContaining({
          sunoRetryCount: 4,
        }),
      )
    })
  })
})
