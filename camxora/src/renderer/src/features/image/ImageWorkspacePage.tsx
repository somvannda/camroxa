import { useEffect, useMemo, useRef, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { CalendarDays, RefreshCw } from 'lucide-react'

import { useImageWorkspaceQuery } from '@/features/image/useImageWorkspaceQuery'
import { getDesktopApi } from '@/shared/api/desktop'
import {
  apiClearImageJobs,
  apiPatchSettings,
  apiRetryImageJobs,
  type ImageJobListItem,
  type MusicHistoryBatchResponse,
  type ProfileResponse,
} from '@/shared/api/platformEndpoints'
import { cn } from '@/shared/lib/utils'
import { Button } from '@/shared/ui/button'
import { Calendar } from '@/shared/ui/calendar'
import { Card } from '@/shared/ui/card'
import { Popover, PopoverContent, PopoverTrigger } from '@/shared/ui/popover'
import { Textarea } from '@/shared/ui/textarea'

type ImageUiSettings = {
  imageBackgroundPrompt: string
  imageThumbnailPrompt: string
}

type QueueRow = {
  key: string
  batchId: string
  songId: string
  songLabel: string
  dateLabel: string
  profileName: string
  role: 'ok' | 'alt'
  bgJob: ImageJobListItem | null
  thJob: ImageJobListItem | null
}

const JOB_STATUS_RANK: Record<string, number> = {
  success: 4,
  running: 3,
  pending: 2,
  failed: 1,
  cancelled: 0,
}

function jobStatusRank(status: string | undefined): number {
  return JOB_STATUS_RANK[String(status || '').toLowerCase()] ?? -1
}

function pickPreferredImageJob(
  current: ImageJobListItem | null,
  candidate: ImageJobListItem,
): ImageJobListItem {
  if (!current) return candidate
  const currentRank = jobStatusRank(current.status)
  const candidateRank = jobStatusRank(candidate.status)
  if (candidateRank !== currentRank) {
    return candidateRank > currentRank ? candidate : current
  }
  const currentStamp = current.updated_at || current.created_at || ''
  const candidateStamp = candidate.updated_at || candidate.created_at || ''
  return candidateStamp >= currentStamp ? candidate : current
}

function buildSongLabels(batches: MusicHistoryBatchResponse[]): Map<string, string> {
  const labels = new Map<string, string>()
  for (const batch of batches) {
    for (const song of batch.songs ?? []) {
      const songId = String(song.song_id || '').trim()
      if (!songId || labels.has(songId)) continue
      const title = String(song.title || '').trim()
      labels.set(songId, title || `Song ${Number(song.batch_index ?? 0) + 1}`)
    }
  }
  return labels
}

function getTodayInputValue(): string {
  const today = new Date()
  const year = today.getFullYear()
  const month = String(today.getMonth() + 1).padStart(2, '0')
  const day = String(today.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function normalizeSettings(settings: Record<string, unknown> | undefined): ImageUiSettings {
  const legacyPrompt = typeof settings?.imagePrompt === 'string' ? settings.imagePrompt : ''
  return {
    imageBackgroundPrompt:
      typeof settings?.imageBackgroundPrompt === 'string' ? settings.imageBackgroundPrompt : legacyPrompt,
    imageThumbnailPrompt:
      typeof settings?.imageThumbnailPrompt === 'string' ? settings.imageThumbnailPrompt : '',
  }
}

function formatJobStatus(status: string | null | undefined): string {
  const normalized = String(status || '').trim().toLowerCase()
  return normalized || '—'
}

function statusChipClass(status: string): string {
  const normalized = status.toLowerCase()
  if (normalized.includes('success')) return 'border-emerald-400/25 bg-emerald-500/10 text-emerald-100'
  if (normalized.includes('running')) return 'border-amber-400/25 bg-amber-500/10 text-amber-100'
  if (normalized.includes('fail')) return 'border-rose-400/25 bg-rose-500/10 text-rose-100'
  if (normalized.includes('pending')) return 'border-white/10 bg-white/5 text-slate-300'
  return 'border-white/10 bg-white/5 text-slate-300'
}

function batchDateLabel(batch: MusicHistoryBatchResponse): string {
  const from = batch.from_date ?? batch.created_at.slice(0, 10)
  const to = batch.to_date ?? batch.updated_at.slice(0, 10)
  return from === to ? from : `${from} → ${to}`
}

function batchIsWithinRange(batch: MusicHistoryBatchResponse, fromDate: string, toDate: string): boolean {
  const from = batch.from_date ?? batch.created_at.slice(0, 10)
  const to = batch.to_date ?? batch.updated_at.slice(0, 10)
  if (fromDate && to < fromDate) return false
  if (toDate && from > toDate) return false
  return true
}

function buildDateValue(date: Date): string {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

export function ImageWorkspacePage(): React.JSX.Element {
  const { data, isLoading, isError, isFetching, refetch } = useImageWorkspaceQuery({ historyLimit: 25 })

  const profiles: ProfileResponse[] = data?.profiles ?? []
  const settings = useMemo(() => normalizeSettings(data?.settings), [data?.settings])
  const historyBatches = data?.musicHistory.batches ?? []
  const imageJobs = data?.imageJobs.items ?? []

  const [fromDate, setFromDate] = useState<string>(() => getTodayInputValue())
  const [toDate, setToDate] = useState<string>(() => getTodayInputValue())
  const [backgroundPrompt, setBackgroundPrompt] = useState('')
  const [thumbnailPrompt, setThumbnailPrompt] = useState('')
  const promptSaveTimer = useRef<number | null>(null)

  const [selectedQueueKey, setSelectedQueueKey] = useState<string | null>(null)
  const [bgPreview, setBgPreview] = useState<string | null>(null)
  const [thumbPreview, setThumbPreview] = useState<string | null>(null)
  const [footerDetail, setFooterDetail] = useState('')
  const [statusLabel, setStatusLabel] = useState('Ready')
  const [workspaceError, setWorkspaceError] = useState<string | null>(null)

  useEffect(() => {
    setBackgroundPrompt(settings.imageBackgroundPrompt)
    setThumbnailPrompt(settings.imageThumbnailPrompt)
  }, [settings.imageBackgroundPrompt, settings.imageThumbnailPrompt])

  const filteredBatches = useMemo(() => {
    return historyBatches.filter((batch) => batchIsWithinRange(batch, fromDate, toDate))
  }, [historyBatches, fromDate, toDate])

  const filteredBatchIds = useMemo(() => filteredBatches.map((batch) => batch.batch_id).filter(Boolean), [filteredBatches])

  const batchMetaById = useMemo(() => {
    return new Map(filteredBatches.map((batch) => [batch.batch_id, batchDateLabel(batch)]))
  }, [filteredBatches])

  const patchSettingsMutation = useMutation({
    mutationFn: async (patch: Record<string, unknown>) => apiPatchSettings(patch),
    onError: () => {
      setWorkspaceError('Unable to save image settings right now.')
    },
  })

  useEffect(() => {
    if (promptSaveTimer.current) {
      window.clearTimeout(promptSaveTimer.current)
    }
    promptSaveTimer.current = window.setTimeout(() => {
      promptSaveTimer.current = null
      void patchSettingsMutation.mutateAsync({
        imageBackgroundPrompt: backgroundPrompt,
        imageThumbnailPrompt: thumbnailPrompt,
      })
    }, 350)

    return () => {
      if (promptSaveTimer.current) {
        window.clearTimeout(promptSaveTimer.current)
      }
    }
  }, [backgroundPrompt, thumbnailPrompt, patchSettingsMutation])

  const retryMutation = useMutation({
    mutationFn: async (jobIds: string[]) => apiRetryImageJobs({ job_ids: jobIds }),
    onSuccess: async () => {
      setWorkspaceError(null)
      setStatusLabel('Retry queued.')
      await refetch()
    },
    onError: () => {
      setStatusLabel('Unable to retry job.')
      setWorkspaceError('Unable to retry image jobs.')
    },
  })

  const clearQueueMutation = useMutation({
    mutationFn: async () => {
      if (!filteredBatchIds.length) {
        throw new Error('No queued batch range is selected to clear.')
      }
      const results = await Promise.all(filteredBatchIds.map((batchId) => apiClearImageJobs({ batch_id: batchId })))
      return results.reduce((total, result) => total + result.deleted, 0)
    },
    onSuccess: async () => {
      setWorkspaceError(null)
      setStatusLabel('Queue cleared for the selected date range.')
      await refetch()
    },
    onError: (error) => {
      setStatusLabel('Unable to clear queue.')
      setWorkspaceError(error instanceof Error ? error.message : 'Unable to clear image queue.')
    },
  })

  const filteredImageJobs = useMemo(() => {
    if (!filteredBatchIds.length) {
      return [] as ImageJobListItem[]
    }
    const allowed = new Set(filteredBatchIds)
    return imageJobs.filter((job) => job.batch_id && allowed.has(job.batch_id))
  }, [filteredBatchIds, imageJobs])

  const groupedQueueRows = useMemo(() => {
    const profileById = new Map(profiles.map((profile) => [profile.id, profile]))
    const songLabels = buildSongLabels(history.batches)
    const rows = new Map<string, QueueRow>()

    filteredImageJobs.forEach((job) => {
      const batchId = job.batch_id || ''
      const songId = job.song_id || ''
      const profileId = job.profile_id || ''
      const role = job.channel_role
      const key = `${batchId}-${songId}-${profileId}-${role}`
      const profileName = profileById.get(profileId)?.name ?? profileId ?? 'Unknown'
      const songLabel = songLabels.get(songId) ?? 'Unknown song'
      const existing = rows.get(key) ?? {
        key,
        batchId,
        songId,
        songLabel,
        dateLabel: batchMetaById.get(batchId) ?? 'Unknown date',
        profileName,
        role,
        bgJob: null,
        thJob: null,
      }
      if (job.kind === 'background') {
        existing.bgJob = pickPreferredImageJob(existing.bgJob, job)
      } else if (job.kind === 'thumbnail') {
        existing.thJob = pickPreferredImageJob(existing.thJob, job)
      }
      rows.set(key, existing)
    })

    return Array.from(rows.values()).sort((a, b) => {
      const byDate = a.dateLabel.localeCompare(b.dateLabel)
      if (byDate !== 0) return byDate
      const bySong = a.songLabel.localeCompare(b.songLabel)
      if (bySong !== 0) return bySong
      const byRole = a.role.localeCompare(b.role)
      if (byRole !== 0) return byRole
      return a.profileName.localeCompare(b.profileName)
    })
  }, [batchMetaById, filteredImageJobs, history.batches, profiles])

  useEffect(() => {
    if (!groupedQueueRows.some((row) => row.key === selectedQueueKey)) {
      setSelectedQueueKey(groupedQueueRows[0]?.key ?? null)
    }
  }, [groupedQueueRows, selectedQueueKey])

  const selectedQueueRow = useMemo(() => {
    if (!selectedQueueKey) {
      return null
    }
    return groupedQueueRows.find((row) => row.key === selectedQueueKey) ?? null
  }, [groupedQueueRows, selectedQueueKey])

  useEffect(() => {
    const run = async () => {
      if (!selectedQueueRow) {
        setBgPreview(null)
        setThumbPreview(null)
        setFooterDetail('')
        return
      }

      const desktop = getDesktopApi()
      const [bgBase64, thBase64] = await Promise.all([
        selectedQueueRow.bgJob?.output_image_path
          ? desktop.files.readFileAsBase64(selectedQueueRow.bgJob.output_image_path)
          : Promise.resolve(null),
        selectedQueueRow.thJob?.output_image_path
          ? desktop.files.readFileAsBase64(selectedQueueRow.thJob.output_image_path)
          : Promise.resolve(null),
      ])
      setBgPreview(bgBase64 ? `data:image/png;base64,${bgBase64}` : null)
      setThumbPreview(thBase64 ? `data:image/png;base64,${thBase64}` : null)
      const detailParts: string[] = []
      if (selectedQueueRow.bgJob?.error) detailParts.push(`BG error: ${selectedQueueRow.bgJob.error}`)
      if (selectedQueueRow.thJob?.error) detailParts.push(`TH error: ${selectedQueueRow.thJob.error}`)
      if (selectedQueueRow.bgJob?.input_image_path) {
        detailParts.push(`BG sample: ${selectedQueueRow.bgJob.input_image_path.split(/[\\/]/).pop()}`)
      }
      if (selectedQueueRow.thJob?.style_reference_path) {
        detailParts.push(`TH style: ${selectedQueueRow.thJob.style_reference_path.split(/[\\/]/).pop()}`)
      }
      setFooterDetail(detailParts.join(' · '))
    }

    void run()
  }, [selectedQueueRow])

  const handleJobDoubleClick = async (job: ImageJobListItem | null) => {
    if (!job) return
    if (job.status === 'failed') {
      await retryMutation.mutateAsync([job.id])
      return
    }
    if (job.status === 'success' && job.output_image_path) {
      await getDesktopApi().files.openPath(job.output_image_path)
    }
  }

  const queueStatusSummary = useMemo(() => {
    const total = groupedQueueRows.length
    if (!total) {
      return filteredBatchIds.length
        ? 'No image jobs yet for this date range.'
        : 'No batches found in the selected date range.'
    }
    const visibleJobs = groupedQueueRows.flatMap((row) =>
      [row.bgJob, row.thJob].filter((job): job is ImageJobListItem => Boolean(job)),
    )
    const pending = visibleJobs.filter((job) => job.status === 'pending').length
    const running = visibleJobs.filter((job) => job.status === 'running').length
    const failed = visibleJobs.filter((job) => job.status === 'failed').length
    const success = visibleJobs.filter((job) => job.status === 'success').length
    return `Rows ${total} · Pending ${pending} · Running ${running} · Failed ${failed} · Ready ${success}`
  }, [filteredBatchIds.length, groupedQueueRows])

  return (
    <div className="grid gap-4">
      {workspaceError ? (
        <Card className="border-rose-500/25 bg-rose-500/10 p-4 text-sm text-rose-200">{workspaceError}</Card>
      ) : null}

      <div className="grid items-stretch gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(320px,1fr)]">
        <Card className="flex h-full flex-col p-4">
          <p className="text-sm font-semibold text-white">Image Controls + Queue</p>
          <p className="mt-1 text-xs text-slate-500">
            Filter by date and use the queue to review background and thumbnail output together.
          </p>

          <div className="mt-4 flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-slate-200">From</span>
              <Popover>
                <PopoverTrigger asChild>
                  <Button type="button" variant="secondary" className="h-8 px-2.5 text-xs">
                    <CalendarDays className="h-4 w-4" />
                    {fromDate}
                  </Button>
                </PopoverTrigger>
                <PopoverContent align="start" className="p-0">
                  <Calendar
                    mode="single"
                    selected={new Date(`${fromDate}T00:00:00`)}
                    onSelect={(date) => {
                      if (date) {
                        setFromDate(buildDateValue(date))
                      }
                    }}
                  />
                </PopoverContent>
              </Popover>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-slate-200">To</span>
              <Popover>
                <PopoverTrigger asChild>
                  <Button type="button" variant="secondary" className="h-8 px-2.5 text-xs">
                    <CalendarDays className="h-4 w-4" />
                    {toDate}
                  </Button>
                </PopoverTrigger>
                <PopoverContent align="start" className="p-0">
                  <Calendar
                    mode="single"
                    selected={new Date(`${toDate}T00:00:00`)}
                    onSelect={(date) => {
                      if (date) {
                        setToDate(buildDateValue(date))
                      }
                    }}
                  />
                </PopoverContent>
              </Popover>
            </div>

            <Button disabled={isFetching} type="button" variant="secondary" onClick={() => void refetch()}>
              <RefreshCw className={cn('h-4 w-4', isFetching && 'animate-spin')} />
              Reload
            </Button>
          </div>

          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            <div className="rounded-xl border border-white/10 bg-slate-950/60 px-3 py-3">
              <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Date Range</p>
              <p className="mt-1 text-sm font-medium text-white">
                {fromDate} → {toDate}
              </p>
            </div>
            <div className="rounded-xl border border-white/10 bg-slate-950/60 px-3 py-3">
              <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Matched Batches</p>
              <p className="mt-1 text-sm font-medium text-white">{filteredBatchIds.length}</p>
            </div>
            <div className="rounded-xl border border-white/10 bg-slate-950/60 px-3 py-3">
              <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Queue Status</p>
              <p className="mt-1 text-sm font-medium text-white">{statusLabel}</p>
            </div>
          </div>

          <div className="mt-4 flex min-h-0 flex-1 flex-col">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-white">Job Queue</p>
                <p className="mt-1 text-xs text-slate-500">Click a row to load both previews on the right.</p>
              </div>
              <p className="text-xs text-slate-400">{queueStatusSummary}</p>
            </div>

            <div className="mt-3 overflow-hidden rounded-2xl border border-white/10 bg-slate-950/50">
              <div className="grid grid-cols-[120px_160px_140px_56px_82px_82px_1fr_1fr] gap-2 bg-slate-950/70 px-3 py-2 text-[10px] uppercase tracking-[0.16em] text-slate-500">
                <span>Date</span>
                <span>Song</span>
                <span>Channel</span>
                <span>Role</span>
                <span>BG</span>
                <span>TH</span>
                <span>BG File</span>
                <span>TH File</span>
              </div>
              <div className="min-h-[320px] flex-1 divide-y divide-white/10 overflow-auto">
                {groupedQueueRows.length ? (
                  groupedQueueRows.map((row) => {
                    const bgStatus = formatJobStatus(row.bgJob?.status)
                    const thStatus = formatJobStatus(row.thJob?.status)
                    return (
                      <button
                        key={row.key}
                        type="button"
                        className={cn(
                          'grid w-full grid-cols-[120px_160px_140px_56px_82px_82px_1fr_1fr] gap-2 px-3 py-2 text-left text-xs text-slate-200 transition',
                          selectedQueueKey === row.key ? 'bg-fuchsia-500/10' : 'hover:bg-white/5',
                        )}
                        onClick={() => setSelectedQueueKey(row.key)}
                      >
                        <span className="truncate text-slate-300">{row.dateLabel}</span>
                        <span className="truncate">{row.songLabel}</span>
                        <span className="truncate">{row.profileName}</span>
                        <span className="uppercase text-slate-300">{row.role}</span>
                        <span
                          className={cn(
                            'inline-flex items-center justify-between gap-1 rounded-lg border px-2 py-1',
                            statusChipClass(bgStatus),
                          )}
                          onDoubleClick={(event) => {
                            event.stopPropagation()
                            void handleJobDoubleClick(row.bgJob)
                          }}
                        >
                          <span className="truncate">{bgStatus}</span>
                        </span>
                        <span
                          className={cn(
                            'inline-flex items-center justify-between gap-1 rounded-lg border px-2 py-1',
                            statusChipClass(thStatus),
                          )}
                          onDoubleClick={(event) => {
                            event.stopPropagation()
                            void handleJobDoubleClick(row.thJob)
                          }}
                        >
                          <span className="truncate">{thStatus}</span>
                        </span>
                        <span className="truncate text-slate-400">{row.bgJob?.output_image_path?.split(/[\\/]/).pop() ?? '—'}</span>
                        <span className="truncate text-slate-400">{row.thJob?.output_image_path?.split(/[\\/]/).pop() ?? '—'}</span>
                      </button>
                    )
                  })
                ) : (
                  <div className="px-4 py-10 text-center text-sm text-slate-500">
                    {isLoading || isError ? 'Loading jobs...' : 'No jobs yet for the selected date range.'}
                  </div>
                )}
              </div>
            </div>

            {footerDetail ? <p className="mt-3 text-xs text-slate-400">{footerDetail}</p> : null}
          </div>

          <div className="mt-auto grid gap-4 pt-5 xl:grid-cols-2">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">Background Prompt</p>
              <Textarea
                className="mt-2 min-h-[112px]"
                placeholder="Guide how the background should evolve from the chosen sample image."
                value={backgroundPrompt}
                onChange={(event) => setBackgroundPrompt(event.target.value)}
              />
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">Thumbnail Prompt</p>
              <Textarea
                className="mt-2 min-h-[112px]"
                placeholder="Guide how the thumbnail should build on the generated background plus text style."
                value={thumbnailPrompt}
                onChange={(event) => setThumbnailPrompt(event.target.value)}
              />
            </div>
          </div>

          <div className="mt-4 flex flex-wrap gap-3">
            <Button
              disabled={clearQueueMutation.isPending || filteredBatchIds.length === 0}
              type="button"
              variant="secondary"
              className="border-rose-500/30 bg-rose-500/10 text-rose-100 hover:border-rose-400/40 hover:bg-rose-500/15"
              onClick={() => {
                if (window.confirm('Clear Image job queue for the current date range? This cannot be undone.')) {
                  void clearQueueMutation.mutateAsync()
                }
              }}
            >
              Clear Queue
            </Button>
          </div>
        </Card>

        <div className="grid min-h-0 gap-4">
          <Card className="flex flex-col p-4">
            <p className="text-sm font-semibold text-white">Background Preview</p>
            <p className="mt-1 text-xs text-slate-500">Pinned from the selected queue row.</p>
            <div className="mt-4 h-[260px] overflow-hidden rounded-2xl border border-white/10 bg-slate-950/60">
              {bgPreview ? (
                <img alt="Background preview" className="h-full w-full object-cover" src={bgPreview} />
              ) : (
                <div className="flex h-full items-center justify-center text-xs text-slate-500">
                  Select a queue row to preview the background output.
                </div>
              )}
            </div>
          </Card>

          <Card className="flex flex-col p-4">
            <p className="text-sm font-semibold text-white">Thumbnail Preview</p>
            <p className="mt-1 text-xs text-slate-500">Pinned from the selected queue row.</p>
            <div className="mt-4 h-[260px] overflow-hidden rounded-2xl border border-white/10 bg-slate-950/60">
              {thumbPreview ? (
                <img alt="Thumbnail preview" className="h-full w-full object-cover" src={thumbPreview} />
              ) : (
                <div className="flex h-full items-center justify-center text-xs text-slate-500">
                  Select a queue row to preview the thumbnail output.
                </div>
              )}
            </div>
          </Card>
        </div>
      </div>

      {isError ? (
        <Card className="border-rose-500/25 bg-rose-500/10 p-4 text-sm text-rose-200">
          Unable to load the Image workspace right now.
        </Card>
      ) : null}

      {!isLoading && !isError && isFetching ? (
        <Card className="border-white/10 bg-white/5 p-4 text-xs text-slate-400">Refreshing image workspace…</Card>
      ) : null}
    </div>
  )
}
