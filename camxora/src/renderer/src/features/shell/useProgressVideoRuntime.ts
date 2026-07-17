import { useEffect, useMemo, useState } from 'react'

import { useVideoWorkspaceQuery } from '@/features/video/useVideoWorkspaceQuery'
import { getDesktopApi } from '@/shared/api/desktop'
import type { ProgressRowResponse } from '@/shared/api/platformEndpoints'
import {
  buildRuntimePresentationMap,
  getProgressRuntimeKey,
  inspectVideoRunEntries,
  type ProgressRuntimePresentation,
  type VideoRunInspection,
} from '@/shared/lib/videoRuntimeInspection'

const EMPTY_PROGRESS_ROWS: ProgressRowResponse[] = []

export function useProgressVideoRuntime(rows: ProgressRowResponse[] | undefined) {
  const desktopApi = getDesktopApi()
  const workspaceQuery = useVideoWorkspaceQuery()
  const [inspections, setInspections] = useState<Record<string, VideoRunInspection>>({})
  const stableRows = rows?.length ? rows : EMPTY_PROGRESS_ROWS

  const inspectionKey = useMemo(
    () =>
      JSON.stringify({
        rows: stableRows.map((row) => [row.meta.batch_id, row.meta.profile_id, row.meta.role, row.meta.run_dir]),
        export: {
          running: workspaceQuery.data?.export.running ?? false,
          mergeRunning: workspaceQuery.data?.export.mergeRunning ?? false,
          outputDir: workspaceQuery.data?.export.outputDir ?? '',
          completedJobs: workspaceQuery.data?.export.completedJobs ?? 0,
          lastOutputPath: workspaceQuery.data?.export.lastOutputPath ?? '',
          lastMergedOutputPath: workspaceQuery.data?.export.lastMergedOutputPath ?? '',
        },
      }),
    [
      stableRows,
      workspaceQuery.data?.export.completedJobs,
      workspaceQuery.data?.export.lastMergedOutputPath,
      workspaceQuery.data?.export.lastOutputPath,
      workspaceQuery.data?.export.mergeRunning,
      workspaceQuery.data?.export.outputDir,
      workspaceQuery.data?.export.running,
    ],
  )

  useEffect(() => {
    let cancelled = false

    async function inspectDirectories() {
      if (!stableRows.length) {
        setInspections((current) => (Object.keys(current).length ? {} : current))
        return
      }

      const results = await Promise.all(
        stableRows.map(async (row) => {
          const directory = String(row.meta.run_dir || '').trim()
          if (!directory) {
            return [getProgressRuntimeKey(row.meta.batch_id, row.meta.profile_id, row.meta.role), null] as const
          }
          const entries = await desktopApi.files.listDirectoryEntries({
            directoryPath: directory,
            maxResults: 500,
          })
          return [
            getProgressRuntimeKey(row.meta.batch_id, row.meta.profile_id, row.meta.role),
            inspectVideoRunEntries(directory, entries),
          ] as const
        }),
      )

      if (cancelled) {
        return
      }

      setInspections(
        Object.fromEntries(
          results.filter((entry): entry is readonly [string, VideoRunInspection] => Boolean(entry[1])),
        ),
      )
    }

    void inspectDirectories()

    return () => {
      cancelled = true
    }
  }, [desktopApi.files, inspectionKey, stableRows])

  const runtimeByKey: Record<string, ProgressRuntimePresentation> = useMemo(
    () => buildRuntimePresentationMap(stableRows, inspections, workspaceQuery.data),
    [inspections, stableRows, workspaceQuery.data],
  )

  return {
    inspections,
    runtimeByKey,
    workspace: workspaceQuery.data,
  }
}
