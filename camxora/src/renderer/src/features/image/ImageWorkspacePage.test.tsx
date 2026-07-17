import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import { ImageWorkspacePage } from '@/features/image/ImageWorkspacePage'

const mockUseImageWorkspaceQuery = vi.fn()
const mockApiPatchSettings = vi.fn()
const mockApiEnqueueImageJobs = vi.fn()
const mockApiRunImageJobs = vi.fn()

vi.mock('@/features/image/useImageWorkspaceQuery', () => ({
  useImageWorkspaceQuery: () => mockUseImageWorkspaceQuery(),
}))

vi.mock('@/shared/api/platformEndpoints', async () => {
  const actual = await vi.importActual<typeof import('@/shared/api/platformEndpoints')>(
    '@/shared/api/platformEndpoints',
  )

  return {
    ...actual,
    apiPatchSettings: (...args: Parameters<typeof actual.apiPatchSettings>) => mockApiPatchSettings(...args),
    apiEnqueueImageJobs: (...args: Parameters<typeof actual.apiEnqueueImageJobs>) => mockApiEnqueueImageJobs(...args),
    apiRunImageJobs: (...args: Parameters<typeof actual.apiRunImageJobs>) => mockApiRunImageJobs(...args),
  }
})

function buildImageWorkspaceData() {
  return {
    me: {
      profile_allowance: 5,
      channel_profile_count: 2,
    },
    profiles: [
      {
        id: 'profile-ok',
        user_id: 'user-1',
        name: 'OK Channel',
        output_resolution: '1920x1080',
        image_config: {},
        youtube_config: {},
      },
    ],
    settings: {
      imageBackgroundPrompt: 'My base background prompt',
      imageThumbnailPrompt: 'My base thumbnail prompt',
      imageBgRandom: false,
      imageThumbRandom: false,
      imageBgSamples: [],
      imageThumbSamples: [],
      imageSamplesDir: 'C:\\samples',
    },
    musicHistory: {
      batches: [
        {
          batch_id: 'batch-1',
          status: 'pending',
          song_count: 1,
          from_date: '2026-06-28',
          to_date: '2026-06-28',
          planned_days: 1,
          ok_profile_id: 'profile-ok',
          ok_profile_name: 'OK Channel',
          alt_profile_id: null,
          alt_profile_name: null,
          created_at: '2026-06-28T00:00:00Z',
          updated_at: '2026-06-28T00:00:00Z',
          songs: [],
        },
      ],
      summary: '1 batches loaded',
      updated_at: '2026-06-28T00:00:00Z',
    },
    progress: {
      rows: [],
      summary: '0',
      updated_at: '2026-06-28T00:00:00Z',
    },
    imageJobs: {
      items: [],
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
      <ImageWorkspacePage />
    </QueryClientProvider>,
  )
}

describe('ImageWorkspacePage (queue beside previews layout)', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-06-28T12:00:00Z'))
    mockApiPatchSettings.mockResolvedValue({})
    mockApiEnqueueImageJobs.mockResolvedValue({ created: 0 })
    mockApiRunImageJobs.mockResolvedValue({ scheduled: 0 })

    mockUseImageWorkspaceQuery.mockReturnValue({
      data: buildImageWorkspaceData(),
      isLoading: false,
      isError: false,
      isFetching: false,
      refetch: vi.fn().mockResolvedValue(undefined),
    })
  })

  afterEach(() => {
    vi.runOnlyPendingTimers()
    vi.setSystemTime(new Date())
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  it('renders dual prompts with the queue beside previews', () => {
    renderPage()

    expect(screen.getByText('Image Controls + Queue')).toBeInTheDocument()
    expect(screen.getByText('Background Prompt')).toBeInTheDocument()
    expect(screen.getByText('Thumbnail Prompt')).toBeInTheDocument()
    expect(screen.getByText('Background Preview')).toBeInTheDocument()
    expect(screen.getByText('Thumbnail Preview')).toBeInTheDocument()
    expect(screen.getByText('Job Queue')).toBeInTheDocument()
    expect(screen.queryByText('Batches')).not.toBeInTheDocument()
  })

  it('hides manual generation CTA', async () => {
    renderPage()

    expect(screen.queryByRole('button', { name: /generate now/i })).not.toBeInTheDocument()
  })
})
