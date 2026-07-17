import { useMemo } from 'react'

import { useSharedMeQuery } from '@/features/shell/useSharedMeQuery'
import { useSharedProfilesQuery } from '@/features/shell/useSharedProfilesQuery'

export function useShellSummaryQuery() {
  const meQuery = useSharedMeQuery()
  const profilesQuery = useSharedProfilesQuery()

  const data = useMemo(() => {
    if (!meQuery.data) {
      return undefined
    }
    return {
      me: meQuery.data,
      profiles: profilesQuery.data ?? [],
    }
  }, [meQuery.data, profilesQuery.data])

  return {
    data,
    isLoading: meQuery.isLoading || profilesQuery.isLoading,
    isError: meQuery.isError,
  }
}
