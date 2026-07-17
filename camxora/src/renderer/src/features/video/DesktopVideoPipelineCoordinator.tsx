import { useEffect, useRef } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'

import { useSharedProfilesQuery } from '@/features/shell/useSharedProfilesQuery'
import { useSharedSettingsQuery } from '@/features/shell/useSharedSettingsQuery'
import { useProgressVideoRuntime } from '@/features/shell/useProgressVideoRuntime'
import { getDesktopApi } from '@/shared/api/desktop'
import {
  apiConsumeLocalVideo,
  apiEnqueueYouTubeMergeUpload,
  apiListProgressRows,
  apiRunYouTubeUploads,
  type ProgressRowResponse,
} from '@/shared/api/platformEndpoints'
import { selectNextAutoVideoCandidate, selectNextAutoYouTubeCandidate } from '@/shared/lib/desktopVideoAutomation'

const EMPTY_PROGRESS_ROWS: ProgressRowResponse[] = []

export function DesktopVideoPipelineCoordinator(): null {
  const queryClient = useQueryClient()
  const desktopApi = getDesktopApi()
  const orchestrationRunningRef = useRef(false)
  const cooldownUntilRef = useRef<Record<string, number>>({})
  const youtubeOrchestrationRunningRef = useRef(false)
  const youtubeCooldownUntilRef = useRef<Record<string, number>>({})

  const settingsQuery = useSharedSettingsQuery()
  const profilesQuery = useSharedProfilesQuery()
  const progressRowsQuery = useQuery({
    queryKey: ['shared-active-progress-rows'],
    queryFn: () =>
      apiListProgressRows({
        limit: 80,
        active_only: true,
      }),
    staleTime: 5_000,
    refetchInterval: 6_000,
  })

  const rows = progressRowsQuery.data?.rows?.length ? progressRowsQuery.data.rows : EMPTY_PROGRESS_ROWS
  const { inspections, runtimeByKey, workspace } = useProgressVideoRuntime(rows)

  useEffect(() => {
    if (orchestrationRunningRef.current) {
      return
    }

    const candidate = selectNextAutoVideoCandidate({
      rows,
      profiles: profilesQuery.data ?? [],
      settings: settingsQuery.data,
      inspections,
      runtimeByKey,
      workspace,
    })

    if (!candidate) {
      return
    }

    const cooldownKey = `${candidate.key}:${candidate.branch}`
    const cooldownUntil = cooldownUntilRef.current[cooldownKey] ?? 0
    if (cooldownUntil > Date.now()) {
      return
    }

    let cancelled = false
    orchestrationRunningRef.current = true

    void (async () => {
      try {
        await desktopApi.video.setTemplate(candidate.templateId)
        if (candidate.branch === 'long' && candidate.outputResolution) {
          await desktopApi.video.setOutputResolution(candidate.outputResolution)
        }
        const profileId = String(candidate.profileId || '').trim()
        const trackCount = Math.max(1, Number(candidate.expectedTracks || 0) || 1)
        // Bill N video exports before local FFmpeg work (plan allowance or wallet).
        await apiConsumeLocalVideo({
          operation_type: 'video',
          count: trackCount,
          channel_profile_id: profileId || null,
          ref_id: `video:${candidate.batchId}:${candidate.role}:${candidate.branch}`,
        })
        const settingsRecord = (settingsQuery.data ?? {}) as Record<string, unknown>
        const autoMergeWanted = Boolean(settingsRecord.autoMergeAfterVideo ?? false)
        const reelMergeOk =
          candidate.branch !== 'reel' || Boolean(settingsRecord.autoReelAfterVideo ?? false)
        let autoMergeAllowed = false
        if (autoMergeWanted && reelMergeOk) {
          try {
            await apiConsumeLocalVideo({
              operation_type: 'video_merge',
              count: 1,
              channel_profile_id: profileId || null,
              ref_id: `video_merge:${candidate.batchId}:${candidate.role}:${candidate.branch}`,
            })
            autoMergeAllowed = true
          } catch (mergeBillingError) {
            // Videos reserved; proceed without merge if merge allowance/wallet is exhausted.
            console.warn('Auto-merge billing blocked', mergeBillingError)
            autoMergeAllowed = false
          }
        }
        await desktopApi.video.startPipelineExport({
          runDir: candidate.runDir,
          backgroundPath: candidate.backgroundPath,
          branch: candidate.branch,
          batchId: candidate.batchId,
          role: candidate.role,
          settings: settingsQuery.data ?? null,
          autoMerge: autoMergeAllowed,
        })
        cooldownUntilRef.current[cooldownKey] = Date.now() + 4_000
        await Promise.all([
          queryClient.invalidateQueries({ queryKey: ['shared-active-progress-rows'] }),
          queryClient.invalidateQueries({ queryKey: ['progress-rows'] }),
          queryClient.invalidateQueries({ queryKey: ['video-workspace'] }),
        ])
      } catch {
        cooldownUntilRef.current[cooldownKey] = Date.now() + 12_000
      } finally {
        if (!cancelled) {
          orchestrationRunningRef.current = false
        }
      }
    })()

    return () => {
      cancelled = true
      orchestrationRunningRef.current = false
    }
  }, [
    desktopApi.video,
    inspections,
    profilesQuery.data,
    queryClient,
    rows,
    runtimeByKey,
    settingsQuery.data,
    workspace,
  ])

  useEffect(() => {
    if (youtubeOrchestrationRunningRef.current) {
      return
    }

    const candidate = selectNextAutoYouTubeCandidate({
      rows,
      profiles: profilesQuery.data ?? [],
      settings: settingsQuery.data,
      inspections,
      runtimeByKey,
    })
    if (!candidate) {
      return
    }

    const cooldownUntil = youtubeCooldownUntilRef.current[candidate.key] ?? 0
    if (cooldownUntil > Date.now()) {
      return
    }

    let cancelled = false
    youtubeOrchestrationRunningRef.current = true

    void (async () => {
      try {
        const enqueueResponse = await apiEnqueueYouTubeMergeUpload(candidate.profileId, {
          batch_id: candidate.batchId,
          role: candidate.role,
          merged_mp4_path: candidate.mergedMp4Path,
        })
        const enqueueStatus = String(enqueueResponse.status || '').trim().toLowerCase()
        if (enqueueStatus === 'blocked') {
          youtubeCooldownUntilRef.current[candidate.key] = Date.now() + 60_000
          return
        }

        await apiRunYouTubeUploads({
          batch_id: candidate.batchId,
          limit: 1,
        })
        youtubeCooldownUntilRef.current[candidate.key] = Date.now() + 8_000
        await Promise.all([
          queryClient.invalidateQueries({ queryKey: ['shared-active-progress-rows'] }),
          queryClient.invalidateQueries({ queryKey: ['progress-rows'] }),
          queryClient.invalidateQueries({ queryKey: ['workflow-progress-rows'] }),
        ])
      } catch {
        youtubeCooldownUntilRef.current[candidate.key] = Date.now() + 20_000
      } finally {
        if (!cancelled) {
          youtubeOrchestrationRunningRef.current = false
        }
      }
    })()

    return () => {
      cancelled = true
      youtubeOrchestrationRunningRef.current = false
    }
  }, [inspections, profilesQuery.data, queryClient, rows, runtimeByKey, settingsQuery.data])

  return null
}
