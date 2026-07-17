import { useQuery } from '@tanstack/react-query'

import { apiGetDashboardStats, apiGetMe, apiListProfiles, apiValidateLicense } from '@/shared/api/platformEndpoints'

export function useDashboardOverviewQuery() {
  return useQuery({
    queryKey: ['dashboard-overview'],
    queryFn: async () => {
      const [me, profiles, license, stats] = await Promise.all([
        apiGetMe(),
        apiListProfiles().catch(() => []),
        apiValidateLicense().catch(() => null),
        apiGetDashboardStats(),
      ])

      return { me, profiles, license, stats }
    },
  })
}

