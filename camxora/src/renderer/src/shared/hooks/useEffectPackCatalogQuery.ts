import { useQuery } from '@tanstack/react-query'

import { getDesktopApi } from '@/shared/api/desktop'

export function useEffectPackCatalogQuery() {
  const desktopApi = getDesktopApi()
  return useQuery({
    queryKey: ['effect-pack-catalog'],
    queryFn: () => desktopApi.effectPacks.listCatalog(),
    staleTime: 15_000,
  })
}
