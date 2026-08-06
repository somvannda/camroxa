import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { FolderOpen, RefreshCw } from 'lucide-react'

import { useProgressRowsQuery } from '@/features/shell/useProgressRowsQuery'
import { useSharedSettingsQuery } from '@/features/shell/useSharedSettingsQuery'
import { useProgressVideoRuntime } from '@/features/shell/useProgressVideoRuntime'
import { getDesktopApi } from '@/shared/api/desktop'
import { apiListPendingMusicDownloads, apiSyncManualImageJobs } from '@/shared/api/platformEndpoints'
import { inspectManualAssetFiles, type ManualAssetInspection } from '@/shared/lib/manualAssetPaths'
import {
  formatChannelLabel,
  formatImagesCompact,
  formatMusicCompact,
  formatVideoCompact,
  formatYoutubeCompact,
  shortBatchLabel,
  stageStatusTone,
} from '@/shared/lib/progressPresentation'
import { cn } from '@/shared/lib/utils'
import { AppSelect } from '@/shared/ui/app-select'
import { Button } from '@/shared/ui/button'
import { Card } from '@/shared/ui/card'
import { DatePickerField } from '@/shared/ui/date-picker-field'
import { InlineToggle } from '@/shared/ui/inline-toggle'

function todayYmd(): string {
  return new Date().toISOString().slice(0, 10)
}

function normalizeImageSourceMode(value: unknown): 'ai' | 'manual' {
  return String(value ?? '').trim().toLowerCase() === 'manual' ? 'manual' : 'ai'
}

function progressApiFetchLimit(displayLimit: number): number {
  const resolved = Math.max(1, Number(displayLimit) || 25)
  return Math.min(100, Math.max(resolved * 5, 50))
}

function matchesProgressStageFilter(effectiveStage: string, stageFilter: string): boolean {
  const normalized = String(effectiveStage || '').trim().toLowerCase()
  const aliases: Record<string, Set<string>> = {
    export: new Set(['export', 'converter']),
    converter: new Set(['export', 'converter']),
    merge: new Set(['merge', 'merger']),
    merger: new Set(['merge', 'merger']),
  }
  const allowed = aliases[stageFilter] ?? new Set([stageFilter])
  return allowed.has(normalized)
}

function getManualInspectionKey(batchId: string, profileId: string, role: string): string {
  return `${batchId}:${profileId}:${role}`
}

function statCard(
  label: string,
  value: number,
  detail: string,
  tone: 'default' | 'warning' | 'danger' = 'default',
): React.JSX.Element {
  return (
    <div
      className={cn(
        'rounded-2xl border px-4 py-3',
        tone === 'danger'
          ? 'border-rose-500/25 bg-rose-500/10'
          : tone === 'warning'
            ? 'border-amber-500/20 bg-amber-500/10'
            : 'border-white/10 bg-slate-950/45',
      )}
    >
      <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
      <p className="mt-1 text-xs text-slate-400">{detail}</p>
    </div>
  )
}

export function ProgressPage(): React.JSX.Element {
  const desktopApi = getDesktopApi()
  const [fromDate, setFromDate] = useState(todayYmd)
  const [toDate, setToDate] = useState(todayYmd)
  const [activeOnly, setActiveOnly] = useState(false)
  const [stageFilter, setStageFilter] = useState('all')
  const [limit, setLimit] = useState(25)
  const [manualInspections, setManualInspections] = useState<Record<string, ManualAssetInspection>>({})
  const [selectedRowKey, setSelectedRowKey] = useState('')

  const filters = useMemo(
    () => ({
      // Over-fetch so Active/Stage can still fill the UI limit after overlays.
      limit: progressApiFetchLimit(limit),
      activeOnly: false,
      fromDate,
      toDate,
    }),
    [fromDate, limit, toDate],
  )

  const { data, isLoading, isError, isFetching, refetch } = useProgressRowsQuery(filters, {
    refetchInterval: activeOnly ? 4_000 : undefined,
  })
  const { runtimeByKey } = useProgressVideoRuntime(data?.rows)
  const settingsQuery = useSharedSettingsQuery()
  const pendingDownloadsQuery = useQuery({
    queryKey: ['pending-music-downloads-visible'],
    queryFn: () => apiListPendingMusicDownloads({ limit: 12 }),
    refetchInterval: 5_000,
    staleTime: 2_000,
  })
  const settings = settingsQuery.data as Record<string, unknown> | undefined
  const imageSourceMode = normalizeImageSourceMode(settings?.imageSourceMode)
  const pendingDownloadItems = pendingDownloadsQuery.data?.items ?? []
  const effectiveRows = useMemo(
    () =>
      (data?.rows ?? []).map((row) => {
        const runtime = runtimeByKey[getManualInspectionKey(row.meta.batch_id, row.meta.profile_id, row.meta.role)]
        return {
          row,
          runtime,
          effectiveStatus: runtime?.status ?? row.status,
          effectiveConverter: runtime?.converter ?? row.converter,
          effectiveMerge: runtime?.merge ?? row.merge,
          effectiveStage: runtime?.stage ?? row.stage,
          effectiveNotes: runtime?.notes ?? row.notes,
        }
      }),
    [data?.rows, runtimeByKey],
  )
  const matchingRows = useMemo(() => {
    let rows = effectiveRows
    if (activeOnly) {
      rows = rows.filter((entry) => !['done', 'completed'].includes(entry.effectiveStage.toLowerCase()))
    }
    if (stageFilter !== 'all') {
      rows = rows.filter((entry) => matchesProgressStageFilter(entry.effectiveStage, stageFilter))
    }
    return rows
  }, [activeOnly, effectiveRows, stageFilter])
  const filteredRows = useMemo(() => matchingRows.slice(0, Math.max(1, limit)), [limit, matchingRows])
  const selectedEntry = useMemo(
    () =>
      filteredRows.find(
        (entry) =>
          getManualInspectionKey(entry.row.meta.batch_id, entry.row.meta.profile_id, entry.row.meta.role) ===
          selectedRowKey,
      ) ?? filteredRows[0] ?? null,
    [filteredRows, selectedRowKey],
  )
  const activeRunCount = useMemo(
    () => matchingRows.filter((entry) => !['done', 'error'].includes(entry.effectiveStage.toLowerCase())).length,
    [matchingRows],
  )
  const failedRunCount = useMemo(
    () =>
      matchingRows.filter(
        (entry) =>
          entry.effectiveStage.toLowerCase() === 'error' || entry.effectiveStatus.toLowerCase() === 'failed',
      ).length,
    [matchingRows],
  )
  const converterOrMergerCount = useMemo(
    () =>
      matchingRows.filter((entry) =>
        ['converter', 'export', 'merger', 'merge'].includes(entry.effectiveStage.toLowerCase()),
      ).length,
    [matchingRows],
  )
  const waitingOnUserCount = useMemo(
    () =>
      imageSourceMode !== 'manual'
        ? 0
        : matchingRows.filter((entry) => {
            const inspection =
              manualInspections[getManualInspectionKey(entry.row.meta.batch_id, entry.row.meta.profile_id, entry.row.meta.role)]
            return entry.effectiveStage.toLowerCase() === 'image' && inspection && !inspection.ready
          }).length,
    [matchingRows, imageSourceMode, manualInspections],
  )
  const syncManualMutation = useMutation({
    mutationFn: async (batchId: string) => apiSyncManualImageJobs({ batch_id: batchId }),
    onSuccess: async () => {
      await refetch()
    },
  })
  const manualInspectionKey = useMemo(
    () =>
      JSON.stringify({
        mode: imageSourceMode,
        rows: (data?.rows ?? []).map((row) => [row.meta.batch_id, row.meta.profile_id, row.meta.role, row.meta.run_dir]),
      }),
    [data?.rows, imageSourceMode],
  )

  useEffect(() => {
    let cancelled = false

    async function inspectManualFolders() {
      if (imageSourceMode !== 'manual' || !data?.rows.length) {
        setManualInspections({})
        return
      }

      const entries = await Promise.all(
        data.rows.map(async (row) => {
          const directory = String(row.meta.run_dir || '').trim()
          if (!directory) {
            return [row.meta.batch_id, null] as const
          }

          const files = await desktopApi.files.listDirectoryImages({ directoryPath: directory, maxResults: 50 })
          return [
            getManualInspectionKey(row.meta.batch_id, row.meta.profile_id, row.meta.role),
            inspectManualAssetFiles(directory, files),
          ] as const
        }),
      )

      if (cancelled) {
        return
      }

      setManualInspections(
        Object.fromEntries(entries.filter((entry): entry is readonly [string, ManualAssetInspection] => Boolean(entry[1]))),
      )
    }

    void inspectManualFolders()

    return () => {
      cancelled = true
    }
  }, [data?.rows, desktopApi.files, imageSourceMode, manualInspectionKey])

  const handleOpenManualFolder = async (inspection: ManualAssetInspection | undefined) => {
    if (!inspection?.directory) {
      return
    }
    await desktopApi.files.ensureDirectory(inspection.directory)
    await desktopApi.files.openPath(inspection.directory)
  }

  const handleSyncManualAssets = async (batchId: string) => {
    if (!batchId || syncManualMutation.isPending) {
      return
    }
    await syncManualMutation.mutateAsync(batchId)
  }

  return (
    <div className="grid gap-4">
      <Card className="p-5">
        <div className="flex flex-wrap items-start gap-3">
          <div className="mr-auto max-w-3xl">
            <p className="text-lg font-semibold text-white">Progress</p>
            <p className="mt-1 text-sm text-slate-400">
              Operational pipeline view for monitoring failures, waiting rows, and recovery actions.
            </p>
            <p className="mt-3 text-xs leading-6 text-slate-500">
              {isLoading ? 'Loading progress rows...' : data?.summary ?? 'Ready'} Desktop MP3 downloading, converter
              truth, and merger truth now read the real desktop runtime when local outputs exist.
            </p>
          </div>

          <DatePickerField className="w-[132px]" label="From" value={fromDate} onChange={setFromDate} />
          <DatePickerField className="w-[132px]" label="To" value={toDate} onChange={setToDate} />
          <InlineToggle className="h-9 px-3 text-[12px]" label="Active only" pressed={activeOnly} onPressedChange={setActiveOnly} />
          <AppSelect
            options={[
              { label: '10 rows', value: '10' },
              { label: '25 rows', value: '25' },
              { label: '50 rows', value: '50' },
            ]}
            placeholder="Limit"
            triggerClassName="h-9 w-[108px] bg-slate-950/70 text-[13px]"
            value={String(limit)}
            onChange={(value) => setLimit(Number(value || 25))}
          />
          <AppSelect
            options={[
              { label: 'All stages', value: 'all' },
              { label: 'Music', value: 'music' },
              { label: 'Image', value: 'image' },
              { label: 'Converter', value: 'converter' },
              { label: 'Merger', value: 'merger' },
              { label: 'YouTube', value: 'youtube' },
              { label: 'Done', value: 'done' },
              { label: 'Error', value: 'error' },
            ]}
            placeholder="Stage"
            triggerClassName="h-9 w-[148px] bg-slate-950/70 text-[13px]"
            value={stageFilter}
            onChange={(value) => setStageFilter(value || 'all')}
          />
          <Button className="h-9 px-3" disabled={isFetching} type="button" variant="secondary" onClick={() => void refetch()}>
            <RefreshCw className={cn('h-4 w-4', isFetching && 'animate-spin')} />
            Refresh
          </Button>
        </div>

        {imageSourceMode === 'manual' ? (
          <div className="mt-4 rounded-2xl border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
            Manual image mode is active. This page is the recovery handoff for missing `background-16x9`,
            `background-9x16`, `thumbnail-16x9`, and `thumbnail-9x16` assets before video work continues.
          </div>
        ) : null}

        <div className="mt-4 grid gap-3 xl:grid-cols-4">
          {statCard('Active Runs', activeRunCount, 'Rows still moving through the pipeline.')}
          {statCard('Converter / Merger', converterOrMergerCount, 'Rows inside real desktop video execution stages.')}
          {statCard('Waiting On User', waitingOnUserCount, 'Manual-image lanes still missing local assets.', 'warning')}
          {statCard('Failed / Blocked', failedRunCount, 'Rows that likely need operator attention.', 'danger')}
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-2 text-xs text-slate-400">
          <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1">
            {filteredRows.length} visible row{filteredRows.length === 1 ? '' : 's'}
          </span>
          <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1">
            {pendingDownloadItems.length} pending desktop download{pendingDownloadItems.length === 1 ? '' : 's'}
          </span>
          <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1">
            {stageFilter === 'all' ? 'All stages' : `Stage: ${stageFilter}`}
          </span>
        </div>
      </Card>

      {isError ? (
        <Card className="border-rose-500/25 bg-rose-500/10 p-6">
          <p className="text-sm text-rose-200">
            Progress data could not be loaded. Check that the API server is running and the `/progress` endpoint is available.
          </p>
        </Card>
      ) : null}

      <Card className="overflow-hidden p-0">
        <div className="border-b border-white/10 px-5 py-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-white">Operational Rows</p>
              <p className="mt-1 text-xs text-slate-400">
                Scan view for active runs. Select a row to inspect converter, merge, and YouTube details below.
              </p>
            </div>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full border-collapse text-left text-sm">
            <thead className="bg-white/5 text-slate-400">
              <tr>
                <th className="px-4 py-3 font-medium">Run</th>
                <th className="px-4 py-3 font-medium">Channel</th>
                <th className="px-4 py-3 font-medium">Stage</th>
                <th className="px-4 py-3 font-medium">Music</th>
                <th className="px-4 py-3 font-medium">Images</th>
                <th className="px-4 py-3 font-medium">Video</th>
                <th className="px-4 py-3 font-medium">YouTube</th>
                <th className="px-4 py-3 font-medium">Updated</th>
              </tr>
            </thead>
            <tbody>
              {filteredRows.length ? (
                filteredRows.map(({ row, effectiveStatus, effectiveConverter, effectiveMerge, effectiveStage }) => {
                  const rowKey = getManualInspectionKey(row.meta.batch_id, row.meta.profile_id, row.meta.role)
                  const tone = stageStatusTone(effectiveStage, effectiveStatus)
                  const selected = selectedEntry?.row.meta.batch_id === row.meta.batch_id
                    && selectedEntry.row.meta.profile_id === row.meta.profile_id
                    && selectedEntry.row.meta.role === row.meta.role
                  return (
                  <tr
                    className={cn(
                      'cursor-pointer border-t border-white/10 align-top hover:bg-white/[0.03]',
                      selected && 'bg-white/[0.05]',
                    )}
                    key={rowKey}
                    onClick={() => setSelectedRowKey(rowKey)}
                  >
                    <td className="px-4 py-3 text-slate-200">
                      <div className="space-y-1">
                        <p>{row.run_date}</p>
                        <p className="text-[11px] text-slate-400">{shortBatchLabel(row.batch)}</p>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-slate-100">{formatChannelLabel(row.channel, row.meta.role)}</td>
                    <td className="px-4 py-3">
                      <span
                        className={cn(
                          'inline-flex rounded-full border px-2 py-1 text-xs',
                          tone === 'danger'
                            ? 'border-rose-500/30 bg-rose-500/15 text-rose-100'
                            : tone === 'success'
                              ? 'border-emerald-500/30 bg-emerald-500/15 text-emerald-100'
                              : tone === 'warning'
                                ? 'border-sky-500/30 bg-sky-500/15 text-sky-100'
                                : 'border-white/10 bg-white/5 text-slate-200',
                        )}
                      >
                        {effectiveStage} · {effectiveStatus}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-300">{formatMusicCompact(row)}</td>
                    <td className="px-4 py-3 text-slate-300">{formatImagesCompact(row)}</td>
                    <td className="px-4 py-3 text-slate-300">{formatVideoCompact(effectiveConverter, effectiveMerge)}</td>
                    <td className="px-4 py-3 text-slate-300">{formatYoutubeCompact(row)}</td>
                    <td className="px-4 py-3 text-slate-400">{row.updated}</td>
                  </tr>
                )})
              ) : (
                <tr>
                  <td className="px-4 py-5 text-slate-400" colSpan={8}>
                    {isLoading ? 'Loading progress rows...' : 'No runs found for the selected operational filters.'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {selectedEntry ? (
        <Card className="p-5">
          <p className="text-sm font-semibold text-white">Row Detail</p>
          <p className="mt-2 text-sm text-slate-200">
            {selectedEntry.row.run_date} · {selectedEntry.row.batch} · {selectedEntry.row.channel} (
            {selectedEntry.row.meta.role}) · {selectedEntry.effectiveStage} / {selectedEntry.effectiveStatus}
          </p>
          <p className="mt-2 text-sm text-slate-400">{selectedEntry.effectiveNotes}</p>
          <div className="mt-4 grid gap-3 md:grid-cols-3">
            <div className="rounded-xl border border-white/10 bg-slate-950/40 p-3">
              <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Converter</p>
              <p className="mt-2 text-sm text-slate-200">{selectedEntry.effectiveConverter || '—'}</p>
            </div>
            <div className="rounded-xl border border-white/10 bg-slate-950/40 p-3">
              <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Merge</p>
              <p className="mt-2 text-sm text-slate-200">{selectedEntry.effectiveMerge || '—'}</p>
            </div>
            <div className="rounded-xl border border-white/10 bg-slate-950/40 p-3">
              <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">YouTube</p>
              <p className="mt-2 text-sm text-slate-200">{formatYoutubeCompact(selectedEntry.row)}</p>
              {selectedEntry.row.meta.youtube_url ? (
                <p className="mt-2 break-all text-xs text-emerald-300">{selectedEntry.row.meta.youtube_url}</p>
              ) : null}
            </div>
          </div>
          {selectedEntry.row.meta.run_dir ? (
            <p className="mt-4 break-all text-xs text-slate-400">Run folder: {selectedEntry.row.meta.run_dir}</p>
          ) : null}
          {imageSourceMode === 'manual' ? (
            (() => {
              const inspection = manualInspections[
                getManualInspectionKey(
                  selectedEntry.row.meta.batch_id,
                  selectedEntry.row.meta.profile_id,
                  selectedEntry.row.meta.role,
                )
              ]
              return inspection ? (
                <div className="mt-4 rounded-xl border border-amber-500/20 bg-amber-500/10 p-3 text-xs text-amber-100">
                  <p className="font-semibold">
                    {inspection.ready
                      ? `Manual assets ready (${inspection.readyCount}/${inspection.total})`
                      : `Waiting for manual assets (${inspection.readyCount}/${inspection.total})`}
                  </p>
                  <p className="mt-1 break-all text-[11px] text-amber-50/85">{inspection.directory}</p>
                  <p className="mt-1 text-[11px] text-amber-50/85">
                    Long: {selectedEntry.row.meta.long_ready ? 'Ready' : 'Missing'} · Reel:{' '}
                    {selectedEntry.row.meta.reel_ready ? 'Ready' : 'Missing'}
                  </p>
                  {!inspection.ready ? (
                    <p className="mt-1 text-[11px] text-amber-50/85">
                      Missing: {inspection.missingLabels.join(', ')}
                    </p>
                  ) : null}
                  <div className="mt-2 flex flex-wrap gap-2">
                    <Button
                      className="h-7 px-2 text-[11px]"
                      size="sm"
                      type="button"
                      variant="secondary"
                      onClick={() => void handleOpenManualFolder(inspection)}
                    >
                      <FolderOpen className="h-3.5 w-3.5" />
                      Open Folder
                    </Button>
                    {inspection.ready && selectedEntry.effectiveStage === 'Image' ? (
                      <Button
                        className="h-7 px-2 text-[11px]"
                        disabled={syncManualMutation.isPending}
                        size="sm"
                        type="button"
                        variant="primary"
                        onClick={() => void handleSyncManualAssets(selectedEntry.row.meta.batch_id)}
                      >
                        {syncManualMutation.isPending ? 'Syncing...' : 'Continue Pipeline'}
                      </Button>
                    ) : null}
                  </div>
                </div>
              ) : (
                <div className="mt-4 rounded-xl border border-white/10 bg-white/5 p-3 text-xs text-slate-300">
                  Loading manual-folder status...
                </div>
              )
            })()
          ) : null}
        </Card>
      ) : null}

      {pendingDownloadItems.length ? (
        <Card className="p-5">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-sm font-semibold text-white">Desktop Download Queue</p>
              <p className="mt-1 text-xs text-slate-400">
                Pending Suno MP3 files are being downloaded locally in the background from the `platform_api` links.
              </p>
            </div>
            <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-200">
              {pendingDownloadItems.length} pending
            </span>
          </div>
          <div className="mt-4 grid gap-3">
            {pendingDownloadItems.map((item) => (
              <div className="rounded-xl border border-white/10 bg-[#081028] p-3 text-xs text-slate-300" key={item.task_id}>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium text-white">{item.title ?? 'Untitled track'}</span>
                  <span className="text-slate-500">#{item.track_number ?? '—'}</span>
                  <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5">
                    {item.batch_id?.slice(-8) ?? 'batch'}
                  </span>
                </div>
                <div className="mt-2 grid gap-2 md:grid-cols-2">
                  <div className="rounded-lg border border-white/10 bg-slate-950/40 px-3 py-2">
                    <p className="font-medium text-slate-100">Primary</p>
                    <p className="mt-1 break-all text-[11px] text-slate-400">{item.primary.target_path ?? 'No target path yet'}</p>
                  </div>
                  <div className="rounded-lg border border-white/10 bg-slate-950/40 px-3 py-2">
                    <p className="font-medium text-slate-100">Secondary</p>
                    <p className="mt-1 break-all text-[11px] text-slate-400">{item.secondary.target_path ?? 'No target path yet'}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      ) : null}
    </div>
  )
}
