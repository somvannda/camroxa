import { useQuery } from '@tanstack/react-query'

import { apiGetSettings } from '@/shared/api/platformEndpoints'

function getSharedSettingsRefetchInterval(): number | false {
  if (typeof document !== 'undefined' && document.hidden) {
    return 120_000
  }
  return 30_000
}

export function useSharedSettingsQuery() {
  return useQuery({
    queryKey: ['shared-settings'],
    queryFn: () => apiGetSettings(),
    staleTime: 20_000,
    refetchInterval: getSharedSettingsRefetchInterval(),
  })
}
