import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import { MusicWorkspacePage } from '@/features/music/MusicWorkspacePage'

const mockUseMusicWorkspaceQuery = vi.fn()
const mockUseBatchStatusQuery = vi.fn()
const mockApiPatchSettings = vi.fn()
const mockApiGenerateDraft = vi.fn()
const mockApiPolishLyrics = vi.fn()
const mockApiCreateBatch = vi.fn()
const mockApiClaimContentPoolItem = vi.fn()
const mockApiFinalizeContentPoolItem = vi.fn()
const mockApiReleaseContentPoolItem = vi.fn()

vi.mock('@/features/music/useMusicWorkspaceQuery', () => ({
  useMusicWorkspaceQuery: () => mockUseMusicWorkspaceQuery(),
}))

vi.mock('@/features/music/useBatchStatusQuery', () => ({
  useBatchStatusQuery: () => mockUseBatchStatusQuery(),
}))

vi.mock('@/shared/api/platformEndpoints', async () => {
  const actual = await vi.importActual<typeof import('@/shared/api/platformEndpoints')>('@/shared/api/platformEndpoints')

  return {
    ...actual,
    apiClaimContentPoolItem: (...args: Parameters<typeof actual.apiClaimContentPoolItem>) => mockApiClaimContentPoolItem(...args),
    apiPatchSettings: (...args: Parameters<typeof actual.apiPatchSettings>) => mockApiPatchSettings(...args),
    apiFinalizeContentPoolItem: (...args: Parameters<typeof actual.apiFinalizeContentPoolItem>) =>
      mockApiFinalizeContentPoolItem(...args),
    apiGenerateDraft: (...args: Parameters<typeof actual.apiGenerateDraft>) => mockApiGenerateDraft(...args),
    apiPolishLyrics: (...args: Parameters<typeof actual.apiPolishLyrics>) => mockApiPolishLyrics(...args),
    apiCreateBatch: (...args: Parameters<typeof actual.apiCreateBatch>) => mockApiCreateBatch(...args),
    apiReleaseContentPoolItem: (...args: Parameters<typeof actual.apiReleaseContentPoolItem>) => mockApiReleaseContentPoolItem(...args),
  }
})

function buildWorkspaceData() {
  return {
    me: {
      credit_balance: 9999,
      profile_allowance: 5,
      channel_profile_count: 2,
    },
    profiles: [
      {
        id: 'profile-ok',
        name: 'Primary Channel',
        folder_name: null,
        run_prefix: null,
        logo_path: null,
        video_template_id: null,
        reel_template_id: null,
        output_resolution: '1920x1080',
        image_config: {},
        youtube_config: {},
      },
      {
        id: 'profile-alt',
        name: 'Secondary Channel',
        folder_name: null,
        run_prefix: null,
        logo_path: null,
        video_template_id: null,
        reel_template_id: null,
        output_resolution: '1920x1080',
        image_config: {},
        youtube_config: {},
      },
    ],
    settings: {
      language: 'en',
      creativity: 55,
      defaultSongCount: 4,
      strictLevel: 3,
      uniquenessHistoryWindow: 100,
      lyricsPolishStrength: 60,
    },
    descriptionOptions: [
      { id: 'desc-1', name: 'Cinematic Pop' },
      { id: 'desc-2', name: 'Indie Ballad' },
    ],
    structureOptions: [
      { id: 'struct-1', name: 'Verse Chorus Bridge' },
      { id: 'struct-2', name: 'Lo-Fi Loop' },
    ],
    history: {
      summary: '1 recent batch · 1 songs loaded',
      updated_at: '2026-06-25T10:00:00Z',
      batches: [
        {
          batch_id: 'batch-1234567890abcd',
          status: 'pending',
          song_count: 1,
          from_date: '2026-06-25',
          to_date: '2026-06-26',
          planned_days: 2,
          ok_profile_id: 'profile-ok',
          ok_profile_name: 'Primary Channel',
          alt_profile_id: 'profile-alt',
          alt_profile_name: 'Secondary Channel',
          created_at: '2026-06-25T10:00:00Z',
          updated_at: '2026-06-25T10:05:00Z',
          songs: [
            {
              song_id: 'song-1',
              batch_index: 0,
              title: 'Test Song',
              album: 'Test Album',
              lyrics: '[Verse]\nHistory lyrics',
              description_id: 'desc-2',
              description_name: 'Indie Ballad',
              structure_id: 'struct-2',
              structure_name: 'Lo-Fi Loop',
              output_dir_ok: 'D:/Music/OK/Test Song',
              output_dir_alt: 'D:/Music/ALT/Test Song',
              status: 'draft_ready',
              suno_status: 'success',
              youtube_status: null,
              downloaded_ok: true,
              downloaded_alt: false,
              image_jobs_completed: 1,
              image_jobs_total: 2,
              created_at: '2026-06-25T10:01:00Z',
              updated_at: '2026-06-25T10:02:00Z',
            },
          ],
        },
      ],
    },
    operationCosts: {
      items: [
        { operation_type: 'lyric', provider: 'deepseek', sub_model: 'deepseek-chat', credits_per_operation: 3, available: true, message: null },
        { operation_type: 'music', provider: 'suno', sub_model: 'V5', credits_per_operation: 7, available: true, message: null },
        { operation_type: 'background_image', provider: 'fal', sub_model: 'flux', credits_per_operation: 5, available: true, message: null },
      ],
    },
  }
}

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
      <MusicWorkspacePage />
    </QueryClientProvider>,
  )
}

describe('MusicWorkspacePage', () => {
  beforeEach(() => {
    mockApiPatchSettings.mockResolvedValue({})
    mockApiClaimContentPoolItem.mockImplementation((kind: string) => {
      if (kind === 'titles') {
        return Promise.resolve({
          kind,
          item: {
            id: 1,
            text: 'Midnight Bloom',
            secondary_text: null,
            used_count: 0,
            reservation_token: 'token-1',
            reserved_by: 'user:music-draft',
            reserved_at: null,
            created_at: null,
          },
        })
      }

      return Promise.resolve({
        kind,
        item: {
          id: 2,
          text: kind === 'albums' ? 'Silver Skyline' : 'We were neon',
          secondary_text: kind === 'openings' ? 'In the blue hour' : null,
          used_count: 0,
          reservation_token: 'token-1',
          reserved_by: 'user:music-draft',
          reserved_at: null,
          created_at: null,
        },
      })
    })
    mockApiFinalizeContentPoolItem.mockResolvedValue({ ok: true })
    mockApiGenerateDraft.mockResolvedValue({
      title: 'Generated Title',
      album: 'Generated Album',
      lyrics: 'Generated lyrics',
    })
    mockApiPolishLyrics.mockResolvedValue({ lyrics: 'Polished lyrics' })
    mockApiCreateBatch.mockResolvedValue({
      batch_id: 'batch-created',
      status: 'pending',
      song_count: 4,
      from_date: '2026-06-25',
      to_date: '2026-06-25',
      planned_days: 1,
    })
    mockApiReleaseContentPoolItem.mockResolvedValue({ ok: true })
    mockUseMusicWorkspaceQuery.mockReturnValue({
      data: buildWorkspaceData(),
      isLoading: false,
      isError: false,
      isFetching: false,
      refetch: vi.fn(),
    })
    mockUseBatchStatusQuery.mockReturnValue({
      data: null,
    })
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('blocks batch creation when the date range is inverted', () => {
    renderPage()

    fireEvent.change(screen.getAllByLabelText(/^From$/i)[0], { target: { value: '2026-06-27' } })
    fireEvent.change(screen.getAllByLabelText(/^To$/i)[0], { target: { value: '2026-06-25' } })

    expect(screen.getAllByText(/choose a valid inclusive date range/i).length).toBeGreaterThan(0)
    expect(screen.getByRole('button', { name: /^generate/i })).toBeDisabled()
  })

  it('renders the python-style music workspace layout and history table', () => {
    renderPage()

    expect(screen.getAllByText(/^description$/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/^structure$/i).length).toBeGreaterThan(0)
    expect(screen.getByRole('heading', { name: /^primary channels$/i })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /^secondary channels$/i })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /^song$/i })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /^history$/i })).toBeInTheDocument()
    expect(screen.getByText(/1 recent batch/i)).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: /^album$/i })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: /^title$/i })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: /^description$/i })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: /^structure$/i })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: /^primary channel$/i })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: /^secondary channel$/i })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: /^suno$/i })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: /^generated$/i })).toBeInTheDocument()
    expect(screen.getByText(/test song/i)).toBeInTheDocument()
    expect(screen.getByText(/test album/i)).toBeInTheDocument()
    expect(screen.getAllByText(/indie ballad/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/lo-fi loop/i).length).toBeGreaterThan(0)
    expect(screen.getByText(/draft: 3 credits/i)).toBeInTheDocument()
    expect(screen.getByText(/polish: 3 credits/i)).toBeInTheDocument()
    expect(screen.getByText(/revisions: 0 credits/i)).toBeInTheDocument()
    expect(screen.getByText(/suno: 7 credits/i)).toBeInTheDocument()
    expect(screen.getByText(/image: 5 credits/i)).toBeInTheDocument()
    expect(screen.getByText(/draft total: 12 credits/i)).toBeInTheDocument()
    expect(screen.getByText(/suno total: 0 credits/i)).toBeInTheDocument()
    expect(screen.getByText(/image total: 0 credits/i)).toBeInTheDocument()
    expect(screen.getByText(/batch total: 12 credits/i)).toBeInTheDocument()
    expect(screen.getByText(/1 day x 1 pair x 4 songs = 4 song jobs/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /draft \(3 credits\)/i })).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /polish \(3 credits\)/i }).length).toBeGreaterThan(0)
    expect(screen.getByRole('button', { name: /revisions \(0 credits\)/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /generate \(12 credits\)/i })).toBeInTheDocument()
    expect(screen.getAllByText(/primary channel/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/secondary channel/i).length).toBeGreaterThan(0)
    expect(screen.getByText(/active pipeline automation currently includes/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^auto-video$/i })).toBeEnabled()
    expect(screen.getByRole('button', { name: /^auto merge$/i })).toBeEnabled()
    expect(screen.getByRole('button', { name: /^auto reel$/i })).toBeEnabled()
    expect(screen.getByRole('button', { name: /^auto-upload$/i })).toBeDisabled()
  })

  it('uses pool seeds as inspiration when generating a draft', async () => {
    renderPage()

    fireEvent.click(screen.getByRole('button', { name: /^draft \(3 credits\)$/i }))

    await waitFor(() =>
      expect(mockApiGenerateDraft).toHaveBeenCalledWith(
        expect.objectContaining({
          description: expect.stringContaining('Inspiration (do not copy words): Midnight Bloom / Silver Skyline'),
        }),
      ),
    )
    expect(mockApiFinalizeContentPoolItem).toHaveBeenCalledTimes(2)
    expect(screen.getByText(/draft seeded from pools and polished into a new result/i)).toBeInTheDocument()
  })

  it('includes image costs without forcing Suno costs when auto image is enabled', async () => {
    renderPage()

    fireEvent.click(screen.getByRole('button', { name: /^auto-gen image$/i }))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /generate \(92 credits\)/i })).toBeInTheDocument()
    })
    expect(screen.getByText(/includes image credits/i)).toBeInTheDocument()
    expect(screen.getByText(/image total: 80 credits/i)).toBeInTheDocument()
    expect(screen.getByText(/suno total: 0 credits/i)).toBeInTheDocument()
    expect(screen.getByText(/batch total: 92 credits/i)).toBeInTheDocument()
  })

  it('adds Suno costs only when Auto-GSuno is enabled', async () => {
    renderPage()

    fireEvent.click(screen.getByRole('button', { name: /^auto-gsuno$/i }))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /generate \(40 credits\)/i })).toBeInTheDocument()
    })
    expect(screen.getByText(/suno total: 28 credits/i)).toBeInTheDocument()
    expect(screen.getByText(/batch total: 40 credits/i)).toBeInTheDocument()
  })

  it('scales generate totals and batch creation by planned days', async () => {
    renderPage()

    fireEvent.click(screen.getByRole('button', { name: /^auto-gsuno$/i }))
    fireEvent.change(screen.getAllByLabelText(/^From$/i)[0], { target: { value: '2026-06-25' } })
    fireEvent.change(screen.getAllByLabelText(/^To$/i)[0], { target: { value: '2026-06-27' } })

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /generate \(120 credits\)/i })).toBeInTheDocument()
    })
    expect(screen.getByText(/3 planned batch runs from 3 days x 1 pair/i)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /generate \(120 credits\)/i }))

    await waitFor(() => {
      expect(mockApiCreateBatch).toHaveBeenCalledTimes(3)
    })
    expect(mockApiCreateBatch).toHaveBeenNthCalledWith(
      1,
      expect.objectContaining({ from_date: '2026-06-25', to_date: '2026-06-25', auto_gsuno: true }),
    )
    expect(mockApiCreateBatch).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({ from_date: '2026-06-26', to_date: '2026-06-26', auto_gsuno: true }),
    )
    expect(mockApiCreateBatch).toHaveBeenNthCalledWith(
      3,
      expect.objectContaining({ from_date: '2026-06-27', to_date: '2026-06-27', auto_gsuno: true }),
    )
  })
})
