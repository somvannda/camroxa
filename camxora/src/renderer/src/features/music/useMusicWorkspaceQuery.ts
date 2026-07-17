import { useQuery } from '@tanstack/react-query'

import {
  apiGetOperationCosts,
  apiGetMe,
  apiGetSettings,
  apiListMusicHistory,
  apiListProfiles,
  apiListPromptDescriptionNames,
  apiListPromptStructureNames,
} from '@/shared/api/platformEndpoints'

export function useMusicWorkspaceQuery() {
  return useQuery({
    queryKey: ['music-workspace'],
    queryFn: async () => {
      const [me, profiles, settings, descriptionOptions, structureOptions, history, operationCosts] = await Promise.all([
        apiGetMe(),
        apiListProfiles(),
        apiGetSettings(),
        apiListPromptDescriptionNames(),
        apiListPromptStructureNames(),
        apiListMusicHistory({ limit: 8 }),
        apiGetOperationCosts().catch(() => ({ items: [] })),
      ])
      return { me, profiles, settings, descriptionOptions, structureOptions, history, operationCosts }
    },
  })
}
