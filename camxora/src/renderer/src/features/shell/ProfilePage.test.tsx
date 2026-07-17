import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import { ProfilePage } from '@/features/shell/ProfilePage'

const mockUseDashboardOverviewQuery = vi.fn()

vi.mock('@/features/shell/useDashboardOverviewQuery', () => ({
  useDashboardOverviewQuery: () => mockUseDashboardOverviewQuery(),
}))

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
      <ProfilePage />
    </QueryClientProvider>,
  )
}

describe('ProfilePage', () => {
  beforeEach(() => {
    mockUseDashboardOverviewQuery.mockReturnValue({
      data: {
        me: {
          id: 'user-1',
          email: 'boss@example.com',
          email_confirmed: true,
          display_name: 'Boss',
          credit_balance: 250,
          plan_name: 'Pro',
          profile_allowance: 5,
          channel_profile_count: 2,
        },
        profiles: [
          {
            id: 'profile-1',
            user_id: 'user-1',
            name: 'OK Channel',
            run_prefix: 'OK',
            output_resolution: '1920x1080',
            image_config: { mode: 'bg_thumb' },
            youtube_config: { visibility: 'public' },
          },
        ],
        license: {
          plan_type: 'Pro',
          profile_allowance: 5,
          monthly_song_quota: 120,
          songs_remaining: 76,
          wallet_balance: 250,
          expiration_date: '2026-12-31T00:00:00Z',
        },
        stats: {
          credits_spent: 480,
          credits_remaining: 250,
          credits_total: 730,
          songs_generated: 44,
          songs_remaining: 76,
          songs_quota: 120,
          images_generated: 19,
          videos_generated: 3,
          usage_by_day: [],
          recent_activity: [],
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
  })

  it('renders live plan, usage, and profile metadata', () => {
    renderPage()

    expect(screen.getByText(/membership/i)).toBeInTheDocument()
    expect(screen.getByText(/activity/i)).toBeInTheDocument()
    expect(screen.getAllByText('120').length).toBeGreaterThan(0)
    expect(screen.getByText(/76 remaining/i)).toBeInTheDocument()
    expect(screen.getByText(/background \+ thumbnail/i)).toBeInTheDocument()
    expect(screen.getAllByText(/^public$/i).length).toBeGreaterThan(0)
    expect(screen.getByText(/images generated/i)).toBeInTheDocument()
  })

  it('shows an empty state when no channel profiles exist yet', () => {
    mockUseDashboardOverviewQuery.mockReturnValue({
      data: {
        me: {
          id: 'user-1',
          email: 'boss@example.com',
          email_confirmed: true,
          display_name: 'Boss',
          credit_balance: 250,
          plan_name: 'Pro',
          profile_allowance: 5,
          channel_profile_count: 0,
        },
        profiles: [],
        license: {
          plan_type: 'Pro',
          profile_allowance: 5,
          monthly_song_quota: 120,
          songs_remaining: 120,
          wallet_balance: 250,
          expiration_date: '2026-12-31T00:00:00Z',
        },
        stats: {
          credits_spent: 0,
          credits_remaining: 250,
          credits_total: 250,
          songs_generated: 0,
          songs_remaining: 120,
          songs_quota: 120,
          images_generated: 0,
          videos_generated: 0,
          usage_by_day: [],
          recent_activity: [],
        },
      },
      isLoading: false,
      isError: false,
      isFetching: false,
      refetch: vi.fn(),
    })

    renderPage()

    expect(screen.getByText(/no channel profiles found yet/i)).toBeInTheDocument()
  })
})
