import { useQuery } from '@tanstack/react-query'

import { apiListProfiles } from '@/shared/api/platformEndpoints'

function getSharedProfilesRefetchInterval(): number | false {
  if (typeof document !== 'undefined' && document.hidden) {
    return 180_000
  }
  return 60_000
}

export function useSharedProfilesQuery() {
  return useQuery({
    queryKey: ['shared-profiles'],
    queryFn: () => apiListProfiles(),
    staleTime: 60_000,
    refetchInterval: getSharedProfilesRefetchInterval(),
  })
}
