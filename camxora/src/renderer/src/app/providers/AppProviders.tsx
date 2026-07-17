import { type PropsWithChildren, useEffect, useMemo } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import { getDesktopApi } from '@/shared/api/desktop'

export function AppProviders({ children }: PropsWithChildren): React.JSX.Element {
  const queryClient = useMemo(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            retry: false,
            refetchOnWindowFocus: false,
            staleTime: 30_000,
          },
        },
      }),
    [],
  )

  useEffect(() => {
    const role = getDesktopApi().isSplash ? 'splash' : 'main'
    document.body.dataset.windowRole = role
    document.documentElement.dataset.windowRole = role
  }, [])

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
}
