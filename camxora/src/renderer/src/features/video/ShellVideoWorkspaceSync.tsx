import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import { getDesktopApi } from '@/shared/api/desktop'

export function ShellVideoWorkspaceSync(): null {
  const queryClient = useQueryClient()
  const desktopApi = getDesktopApi()

  useEffect(() => {
    return desktopApi.video.onWorkspaceEvent((payload) => {
      void desktopApi.video.getWorkspaceState().then((workspace) => {
        queryClient.setQueryData(['video-workspace'], workspace)
      })

      if (payload.reason === 'export') {
        void Promise.all([
          queryClient.invalidateQueries({ queryKey: ['shared-active-progress-rows'] }),
          queryClient.invalidateQueries({ queryKey: ['progress-rows'] }),
          queryClient.invalidateQueries({ queryKey: ['workflow-progress-rows'] }),
        ])
      }
    })
  }, [desktopApi.video, queryClient])

  return null
}
