import { useQuery } from '@tanstack/react-query'

import { apiListProgressRows } from '@/shared/api/platformEndpoints'

export type ProgressFilters = {
  limit: number
  activeOnly: boolean
  fromDate: string
  toDate: string
}

type UseProgressRowsQueryOptions = {
  refetchInterval?: number | false
}

function getDefaultProgressRefetchInterval(filters: ProgressFilters): number | false {
  if (typeof document !== 'undefined' && document.hidden) {
    return 15_000
  }

  if (filters.activeOnly) {
    return 4_000
  }

  return 12_000
}

export function useProgressRowsQuery(filters: ProgressFilters, options?: UseProgressRowsQueryOptions) {
  return useQuery({
    queryKey: ['progress-rows', filters],
    queryFn: () =>
      apiListProgressRows({
        limit: filters.limit,
        active_only: filters.activeOnly,
        from_date: filters.fromDate || undefined,
        to_date: filters.toDate || undefined,
      }),
    refetchInterval: options?.refetchInterval ?? getDefaultProgressRefetchInterval(filters),
  })
}
