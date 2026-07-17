import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import { HomePage } from '@/features/shell/HomePage'

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
      <HomePage />
    </QueryClientProvider>,
  )
}

describe('HomePage', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  it('shows loading placeholders while dashboard data is loading', () => {
    mockUseDashboardOverviewQuery.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      isFetching: false,
      refetch: vi.fn(),
    })

    renderPage()

    expect(screen.getByText(/weekly usage/i)).toBeInTheDocument()
    expect(screen.getByText(/remaining this month/i)).toBeInTheDocument()
    expect(screen.getAllByText('--').length).toBeGreaterThan(0)
    expect(screen.queryByRole('button', { name: /refresh/i })).not.toBeInTheDocument()
  })

  it('shows a backend error banner when dashboard loading fails', () => {
    mockUseDashboardOverviewQuery.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      isFetching: false,
      refetch: vi.fn(),
    })

    renderPage()

    expect(screen.getByText(/unable to load dashboard statistics right now/i)).toBeInTheDocument()
  })
})
