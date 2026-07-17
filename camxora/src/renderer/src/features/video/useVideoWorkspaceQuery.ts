import { useQuery } from '@tanstack/react-query'

import { getDesktopApi } from '@/shared/api/desktop'

export function useVideoWorkspaceQuery() {
  return useQuery({
    queryKey: ['video-workspace'],
    queryFn: () => getDesktopApi().video.getWorkspaceState(),
    staleTime: 10_000,
    refetchInterval: (query) => (query.state.data?.export.running ? 1500 : false),
  })
}
