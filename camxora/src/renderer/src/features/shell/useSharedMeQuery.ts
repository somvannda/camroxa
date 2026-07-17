import { useQuery } from '@tanstack/react-query'

import { apiGetMe } from '@/shared/api/platformEndpoints'

function getSharedMeRefetchInterval(): number | false {
  if (typeof document !== 'undefined' && document.hidden) {
    return 120_000
  }
  return 60_000
}

export function useSharedMeQuery() {
  return useQuery({
    queryKey: ['shared-me'],
    queryFn: () => apiGetMe(),
    staleTime: 30_000,
    refetchInterval: getSharedMeRefetchInterval(),
  })
}
