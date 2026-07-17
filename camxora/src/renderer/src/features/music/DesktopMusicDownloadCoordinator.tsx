import { useEffect, useRef } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'

import { getDesktopApi } from '@/shared/api/desktop'
import {
  apiListPendingMusicDownloads,
  apiSyncMusicDownloads,
  type MusicDownloadSyncItemRequest,
} from '@/shared/api/platformEndpoints'
import type { MusicTrackDownloadRequest } from '@/shared/types/desktop'

export function DesktopMusicDownloadCoordinator(): null {
  const queryClient = useQueryClient()
  const desktopApi = getDesktopApi()
  const syncRunningRef = useRef(false)

  const pendingDownloadsQuery = useQuery({
    queryKey: ['pending-music-downloads'],
    queryFn: () => apiListPendingMusicDownloads({ limit: 24 }),
    staleTime: 2_000,
    refetchInterval: (query) => (query.state.data?.items?.length ? 4_000 : 12_000),
  })

  useEffect(() => {
    if (syncRunningRef.current) {
      return
    }
    const pendingItems = pendingDownloadsQuery.data?.items ?? []
    if (!pendingItems.length) {
      return
    }

    const requests: MusicTrackDownloadRequest[] = []
    const ensuredDirs = new Set<string>()
    for (const item of pendingItems) {
      if (item.primary.download_url && item.primary.output_dir && item.primary.target_path && !item.primary.downloaded) {
        if (!ensuredDirs.has(item.primary.output_dir)) {
          await desktopApi.files.ensureDirectory(item.primary.output_dir)
          ensuredDirs.add(item.primary.output_dir)
        }
        requests.push({
          taskId: item.task_id,
          channel: 'primary',
          url: item.primary.download_url,
          outputDir: item.primary.output_dir,
          targetPath: item.primary.target_path,
        })
      }
      if (item.secondary.download_url && item.secondary.output_dir && item.secondary.target_path && !item.secondary.downloaded) {
        if (!ensuredDirs.has(item.secondary.output_dir)) {
          await desktopApi.files.ensureDirectory(item.secondary.output_dir)
          ensuredDirs.add(item.secondary.output_dir)
        }
        requests.push({
          taskId: item.task_id,
          channel: 'secondary',
          url: item.secondary.download_url,
          outputDir: item.secondary.output_dir,
          targetPath: item.secondary.target_path,
        })
      }
    }

    if (!requests.length) {
      return
    }

    let cancelled = false
    syncRunningRef.current = true

    void (async () => {
      try {
        const results = await desktopApi.files.downloadMusicTracks({
          items: requests,
          retryCount: 3,
        })
        if (cancelled) {
          return
        }

        const syncMap = new Map<string, MusicDownloadSyncItemRequest>()
        for (const result of results) {
          if (!result.ok) {
            continue
          }
          const current = syncMap.get(result.taskId) ?? { task_id: result.taskId }
          if (result.channel === 'primary') {
            current.downloaded_primary = true
            current.output_dir_primary = result.outputDir
          } else {
            current.downloaded_secondary = true
            current.output_dir_secondary = result.outputDir
          }
          syncMap.set(result.taskId, current)
        }

        if (!syncMap.size) {
          return
        }

        await apiSyncMusicDownloads([...syncMap.values()])
        await Promise.all([
          queryClient.invalidateQueries({ queryKey: ['pending-music-downloads'] }),
          queryClient.invalidateQueries({ queryKey: ['pending-music-downloads-visible'] }),
          queryClient.invalidateQueries({ queryKey: ['music-workspace'] }),
          queryClient.invalidateQueries({ queryKey: ['progress-rows'] }),
          queryClient.invalidateQueries({ queryKey: ['video-workspace'] }),
          queryClient.invalidateQueries({ queryKey: ['image-workspace'] }),
        ])
      } finally {
        if (!cancelled) {
          syncRunningRef.current = false
        }
      }
    })()

    return () => {
      cancelled = true
      syncRunningRef.current = false
    }
  }, [desktopApi.files, pendingDownloadsQuery.data?.items, queryClient])

  return null
}
