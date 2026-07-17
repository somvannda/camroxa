import { useQuery } from '@tanstack/react-query'

import {
  apiGetMe,
  apiGetSettings,
  apiListImageJobs,
  apiListMusicHistory,
  apiListProfiles,
  apiListProgressRows,
} from '@/shared/api/platformEndpoints'

export function useImageWorkspaceQuery(input?: { historyLimit?: number }) {
  return useQuery({
    queryKey: ['image-workspace', input?.historyLimit ?? 25],
    queryFn: async () => {
      const [me, profiles, progress, imageJobs, settings, musicHistory] = await Promise.all([
        apiGetMe(),
        apiListProfiles(),
        apiListProgressRows({
          limit: 25,
          active_only: false,
        }),
        apiListImageJobs({ limit: 200 }),
        apiGetSettings(),
        apiListMusicHistory({ limit: input?.historyLimit ?? 25 }),
      ])
      return { me, profiles, progress, imageJobs, settings, musicHistory }
    },
    refetchInterval: 4000,
  })
}
