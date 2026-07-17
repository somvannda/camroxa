import { useEffect, useMemo, useState } from 'react'
import { CheckCircle2, Circle, GitMerge, Image, LoaderCircle, Music4, RefreshCw, Video, XCircle, Youtube } from 'lucide-react'

import { useProgressRowsQuery } from '@/features/shell/useProgressRowsQuery'
import { useProgressVideoRuntime } from '@/features/shell/useProgressVideoRuntime'
import type { ProgressRowResponse } from '@/shared/api/platformEndpoints'
import { cn } from '@/shared/lib/utils'
import { Button } from '@/shared/ui/button'
import { Card } from '@/shared/ui/card'
import { DatePickerField } from '@/shared/ui/date-picker-field'
import { InlineToggle } from '@/shared/ui/inline-toggle'

function todayYmd(): string {
  return new Date().toISOString().slice(0, 10)
}

function parseDateTime(value: string | null): Date | null {
  if (!value) {
    return null
  }
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

function formatDuration(start: string | null, end: string | null): string {
  const startDate = parseDateTime(start)
  const endDate = parseDateTime(end)
  if (!startDate || !endDate) {
    return '--'
  }

  const seconds = Math.max(0, Math.round((endDate.getTime() - startDate.getTime()) / 1000))
  if (seconds < 60) {
    return `${seconds}s`
  }
  return `${(seconds / 60).toFixed(1)} min`
}

type WorkflowStepState = 'done' | 'running' | 'partial' | 'inactive' | 'failed'

type WorkflowStep = {
  key: string
  title: string
  shortTitle: string
  percent: number
  state: WorkflowStepState
  duration: string
  details: string[]
  icon: React.ComponentType<{ className?: string }>
}

function clampPercent(value: number): number {
  return Math.max(0, Math.min(100, Math.round(value)))
}

function normalizeKey(value: string | null | undefined): string {
  return String(value || '')
    .trim()
    .toLowerCase()
}

function isActiveVerbStatus(status: string): boolean {
  return [
    'running',
    'rendering',
    'generating',
    'downloading',
    'converting',
    'merging',
    'uploading',
    'processing',
    'queued',
  ].includes(normalizeKey(status))
}

function looksPartialText(value: string): boolean {
  const text = normalizeKey(value)
  return text.includes('pending') || text.includes('partial') || /\/\s*0\b/.test(text) || /\b0\//.test(text)
}

function buildWorkflowSteps(
  row: ProgressRowResponse | null,
  runtime?: {
    converter: string
    merge: string
    stage: string
    status: string
    converterPercent: number
    mergePercent: number
  },
): WorkflowStep[] {
  if (!row) {
    return [
      { key: 'music', title: 'Music Generation', shortTitle: 'Music', percent: 0, state: 'inactive', duration: '--', details: ['No run selected'], icon: Music4 },
      { key: 'image', title: 'Background + Thumbnail', shortTitle: 'Image', percent: 0, state: 'inactive', duration: '--', details: ['No run selected'], icon: Image },
      { key: 'converter', title: 'Convert (MP4)', shortTitle: 'Convert', percent: 0, state: 'inactive', duration: '--', details: ['No run selected'], icon: Video },
      { key: 'merger', title: 'Merger', shortTitle: 'Merger', percent: 0, state: 'inactive', duration: '--', details: ['No run selected'], icon: GitMerge },
      { key: 'youtube', title: 'YouTube Upload', shortTitle: 'YouTube', percent: 0, state: 'inactive', duration: '--', details: ['No run selected'], icon: Youtube },
    ]
  }

  const expected = Math.max(1, row.meta.expected)
  const musicPercent = clampPercent((row.meta.saved / expected) * 100)
  const bgPercent = row.meta.bg_total > 0 ? row.meta.bg_ready / row.meta.bg_total : 0
  const thPercent = row.meta.th_total > 0 ? row.meta.th_ready / row.meta.th_total : 0
  const imagePercent = clampPercent(((bgPercent + thPercent) / 2) * 100)
  const youtubePercent =
    row.meta.youtube_success > 0 ? 100 : row.meta.youtube_pending > 0 ? 50 : row.meta.youtube_failed > 0 ? 100 : 0
  const downstreamComplete = row.meta.youtube_success > 0 || row.stage === 'Done'
  const converterPercent = downstreamComplete ? 100 : runtime?.converterPercent ?? 0
  const mergePercent = downstreamComplete ? 100 : runtime?.mergePercent ?? 0

  const effectiveStage = runtime?.stage ?? row.stage
  const effectiveStatus = runtime?.status ?? row.status
  const stage = normalizeKey(effectiveStage)
  const failed = stage === 'error' || normalizeKey(effectiveStatus) === 'failed'
  const converterText = runtime?.converter ?? row.converter
  const mergeText = runtime?.merge ?? row.merge

  const stateFor = (stepKey: string, percent: number, detailText: string): WorkflowStepState => {
    if (failed && ['music', 'image', 'converter', 'merger', 'youtube'].includes(stepKey) && stage === stepKey) {
      return 'failed'
    }
    const order = ['music', 'image', 'converter', 'merger', 'youtube']
    const currentIndex = order.indexOf(stage)
    const stepIndex = order.indexOf(stepKey)
    if (normalizeKey(row.stage) === 'done' || stage === 'done') {
      return 'done'
    }
    if (failed && currentIndex < 0) {
      return 'failed'
    }
    if (currentIndex < 0) {
      return percent >= 100 ? 'done' : 'inactive'
    }
    if (stepIndex < currentIndex) {
      return 'done'
    }
    if (stepIndex === currentIndex) {
      if (failed) {
        return 'failed'
      }
      if (percent >= 100) {
        return 'done'
      }
      if (isActiveVerbStatus(effectiveStatus)) {
        return 'running'
      }
      if (percent > 0 || looksPartialText(detailText) || normalizeKey(effectiveStatus) === 'partial') {
        return 'partial'
      }
      return 'running'
    }
    return 'inactive'
  }

  const youtubeDetail = formatUploadStatus(row)

  return [
    {
      key: 'music',
      title: 'Music Generation',
      shortTitle: 'Music',
      percent: musicPercent,
      state: stateFor('music', musicPercent, `${row.meta.saved}/${expected}`),
      duration: formatDuration(row.meta.music_started_at, row.meta.music_updated_at),
      details: [`${row.meta.saved}/${expected} songs`, stage === 'music' ? resolveRunStatusLabel(effectiveStage, effectiveStatus, row) : '--'],
      icon: Music4,
    },
    {
      key: 'image',
      title: 'Background + Thumbnail',
      shortTitle: 'Image',
      percent: imagePercent,
      state: stateFor('image', imagePercent, row.image),
      duration: formatDuration(row.meta.image_started_at, row.meta.image_updated_at),
      details: [row.image, stage === 'image' ? resolveRunStatusLabel(effectiveStage, effectiveStatus, row) : '--'],
      icon: Image,
    },
    {
      key: 'converter',
      title: 'Convert (MP4)',
      shortTitle: 'Convert',
      percent: converterPercent,
      state: stateFor('converter', converterPercent, converterText),
      duration: '--',
      details: [converterText, stage === 'converter' ? resolveRunStatusLabel(effectiveStage, effectiveStatus, row, converterText, mergeText) : '--'],
      icon: Video,
    },
    {
      key: 'merger',
      title: 'Merger',
      shortTitle: 'Merger',
      percent: mergePercent,
      state: stateFor('merger', mergePercent, mergeText),
      duration: '--',
      details: [mergeText, stage === 'merger' ? resolveRunStatusLabel(effectiveStage, effectiveStatus, row, converterText, mergeText) : '--'],
      icon: GitMerge,
    },
    {
      key: 'youtube',
      title: 'YouTube Upload',
      shortTitle: 'YouTube',
      percent: youtubePercent,
      state: stateFor('youtube', youtubePercent, youtubeDetail),
      duration: formatDuration(row.meta.youtube_created_at, row.meta.youtube_updated_at),
      details: [youtubeDetail, stage === 'youtube' ? youtubeDetail : '--'],
      icon: Youtube,
    },
  ]
}

function stateClasses(state: WorkflowStepState): string {
  switch (state) {
    case 'done':
      return 'border-emerald-500/35 bg-emerald-500/[0.08] text-emerald-100'
    case 'running':
      return 'border-sky-500/40 bg-sky-500/[0.10] text-sky-100 ring-1 ring-sky-400/20'
    case 'partial':
      return 'border-sky-500/25 bg-sky-500/[0.06] text-sky-100/90'
    case 'failed':
      return 'border-rose-500/40 bg-rose-500/[0.10] text-rose-100'
    default:
      return 'border-white/8 bg-[#081028]/55 text-slate-400 opacity-80'
  }
}

function stateLabel(state: WorkflowStepState): string {
  switch (state) {
    case 'done':
      return 'Done'
    case 'running':
      return 'Running'
    case 'partial':
      return 'Partial'
    case 'failed':
      return 'Failed'
    default:
      return 'Waiting'
  }
}

function stateBadgeClasses(state: WorkflowStepState): string {
  switch (state) {
    case 'done':
      return 'border-emerald-500/30 bg-emerald-500/15 text-emerald-100'
    case 'running':
      return 'border-sky-500/35 bg-sky-500/15 text-sky-100'
    case 'partial':
      return 'border-sky-500/25 bg-sky-500/10 text-sky-200'
    case 'failed':
      return 'border-rose-500/35 bg-rose-500/15 text-rose-100'
    default:
      return 'border-white/10 bg-white/5 text-slate-400'
  }
}

function progressFillClasses(state: WorkflowStepState): string {
  switch (state) {
    case 'done':
      return 'bg-emerald-400'
    case 'running':
      return 'bg-sky-400'
    case 'partial':
      return 'bg-sky-400/70'
    case 'failed':
      return 'bg-rose-400'
    default:
      return 'bg-slate-500'
  }
}

function stepEmptyHint(step: WorkflowStep): string | null {
  if (step.state !== 'inactive') {
    return null
  }
  if (step.key === 'merger') {
    return 'Waiting for converter outputs before merge can start.'
  }
  if (step.key === 'youtube') {
    return 'Waiting — upload starts after the long merged deliverable is ready.'
  }
  if (step.key === 'converter') {
    return 'Waiting for music and image assets to be ready.'
  }
  if (step.key === 'image') {
    return 'Waiting for music downloads to finish.'
  }
  return null
}

function detailLooksEmpty(value: string): boolean {
  const normalized = value.trim().toLowerCase()
  return !normalized || normalized === '--' || normalized === 'empty' || normalized === 'n/a' || normalized === 'none'
}

type LaneEntry = {
  key: string
  row: ProgressRowResponse
  runtime: {
    converter: string
    merge: string
    stage: string
    status: string
    notes: string
    converterPercent: number
    mergePercent: number
  } | undefined
  effectiveStage: string
  effectiveStatus: string
}

function formatRoleLabel(role: string): string {
  return String(role || '').trim().toLowerCase() === 'secondary' ? 'Secondary' : 'Primary'
}

/**
 * Run-level status vocabulary:
 * - "Completed" only when the lane stage is Done
 * - Convert/Merger with unfinished branches → Partial
 * - YouTube with no success/URL → Waiting / Not started (never Completed)
 * - Otherwise preserve active verbs; rewrite premature Completed → Partial
 */
function resolveRunStatusLabel(
  stage: string,
  status: string,
  row: ProgressRowResponse,
  converterText?: string,
  mergeText?: string,
): string {
  const stageKey = normalizeKey(stage)
  const statusKey = normalizeKey(status)

  if (stageKey === 'error' || statusKey === 'failed') {
    return 'Failed'
  }
  if (stageKey === 'done') {
    return 'Completed'
  }

  if (stageKey === 'youtube') {
    return formatUploadStatus(row)
  }

  const converter = converterText ?? row.converter
  const merge = mergeText ?? row.merge

  if (stageKey === 'converter') {
    if (isActiveVerbStatus(status)) {
      return status.trim() || 'Converting'
    }
    if (statusKey === 'partial' || looksPartialText(converter) || (statusKey === 'completed' && !looksCompleteBranchPair(converter))) {
      return 'Partial'
    }
    // Converter finished locally, but the run is not Done yet.
    if (statusKey === 'completed') {
      return 'Ready'
    }
  }

  if (stageKey === 'merger') {
    if (isActiveVerbStatus(status)) {
      return status.trim() || 'Merging'
    }
    if (statusKey === 'partial' || looksPartialText(merge)) {
      return 'Partial'
    }
    // Merger outputs ready, but YouTube/Done has not closed the lane.
    if (statusKey === 'completed') {
      return looksCompleteMergePair(merge) ? 'Ready' : 'Partial'
    }
  }

  // Never show Completed for an incomplete run; fall back to Ready/Partial.
  if (statusKey === 'completed' || statusKey === 'done') {
    return 'Ready'
  }

  if (statusKey === 'partial') {
    return 'Partial'
  }

  return String(status || '').trim() || 'Waiting'
}

function looksCompleteBranchPair(text: string): boolean {
  const match = String(text || '').match(/long\s+(\d+)\s*\/\s*(\d+)\s*·\s*reel\s+(\d+)\s*\/\s*(\d+)/i)
  if (!match) {
    return false
  }
  const longReady = Number(match[1])
  const longTotal = Number(match[2])
  const reelReady = Number(match[3])
  const reelTotal = Number(match[4])
  return longReady >= longTotal && reelReady >= reelTotal && longTotal > 0
}

function looksCompleteMergePair(text: string): boolean {
  const normalized = normalizeKey(text)
  if (!normalized) {
    return false
  }
  if (normalized.includes('pending')) {
    return false
  }
  return normalized.includes('long merged') && (normalized.includes('reel merged') || normalized.includes('reel single') || normalized.includes('not required'))
}

function formatUploadStatus(row: ProgressRowResponse): string {
  if (row.meta.youtube_success > 0 || Boolean(row.meta.youtube_url)) {
    return 'Uploaded'
  }
  if (row.meta.youtube_failed > 0 || normalizeKey(row.meta.youtube_status) === 'failed') {
    return 'Failed'
  }
  if (normalizeKey(row.meta.youtube_status) === 'blocked') {
    return 'Blocked'
  }
  if (row.meta.youtube_pending > 0 || ['uploading', 'queued', 'processing'].includes(normalizeKey(row.meta.youtube_status))) {
    return 'Uploading'
  }
  if (normalizeKey(row.youtube) === 'ready') {
    return 'Ready'
  }
  return 'Not started'
}

function stageToneClasses(stage: string, statusLabel: string): string {
  const normalizedStage = normalizeKey(stage)
  const normalizedStatus = normalizeKey(statusLabel)
  if (normalizedStage === 'error' || normalizedStatus === 'failed') {
    return 'border-rose-500/30 bg-rose-500/10 text-rose-100'
  }
  if (normalizedStage === 'done' || normalizedStatus === 'completed' || normalizedStatus === 'uploaded') {
    return 'border-emerald-500/30 bg-emerald-500/10 text-emerald-100'
  }
  if (normalizedStatus === 'partial' || normalizedStatus === 'ready' || normalizedStatus === 'waiting' || normalizedStatus === 'not started') {
    return 'border-sky-500/20 bg-sky-500/[0.08] text-sky-100'
  }
  if (normalizedStage === 'converter' || normalizedStage === 'merger' || isActiveVerbStatus(statusLabel)) {
    return 'border-sky-500/30 bg-sky-500/10 text-sky-100'
  }
  return 'border-white/10 bg-white/5 text-slate-200'
}

function laneNeedsAttention(entry: LaneEntry): boolean {
  const stage = normalizeKey(entry.effectiveStage)
  const status = normalizeKey(entry.effectiveStatus)
  const row = entry.row
  const mergeText = normalizeKey(entry.runtime?.merge ?? row.merge)
  const youtubeStatus = normalizeKey(row.meta.youtube_status)
  const bgStatus = normalizeKey(row.meta.bg_status)
  const thStatus = normalizeKey(row.meta.th_status)

  if (stage === 'error' || status === 'failed') {
    return true
  }
  if (row.meta.youtube_failed > 0 || youtubeStatus === 'failed' || youtubeStatus === 'blocked') {
    return true
  }
  if (bgStatus === 'failed' || thStatus === 'failed') {
    return true
  }
  if (mergeText.includes('blocked')) {
    return true
  }

  // Pending image blockers while the lane is on (or past) image work.
  const imagesIncomplete =
    (row.meta.bg_total > 0 && row.meta.bg_ready < row.meta.bg_total) ||
    (row.meta.th_total > 0 && row.meta.th_ready < row.meta.th_total)
  if (imagesIncomplete && ['image', 'converter', 'merger', 'youtube'].includes(stage)) {
    return true
  }

  // Merger waiting because branch outputs are incomplete.
  if (stage === 'merger' && (mergeText.includes('pending') || status === 'partial')) {
    return true
  }

  return false
}

function buildCurrentFocus(row: ProgressRowResponse, runtime: LaneEntry['runtime']): string {
  const stage = normalizeKey(runtime?.stage ?? row.stage)
  if (stage === 'music') {
    return row.meta.download_pending > 0
      ? `Waiting on ${row.meta.download_pending} remaining desktop MP3 download(s) before downstream video work can begin.`
      : 'Music generation is still finishing before the downstream pipeline advances.'
  }
  if (stage === 'image') {
    if (!row.meta.long_ready || !row.meta.reel_ready) {
      return 'Waiting for the required long/reel background and thumbnail assets to become ready.'
    }
    return 'Image generation is finishing and the lane is preparing the video inputs.'
  }
  if (stage === 'converter') {
    const converter = runtime?.converter ?? row.converter
    if (looksPartialText(converter) || normalizeKey(runtime?.status ?? row.status) === 'partial') {
      return 'Convert is partial — long and reel exports finish independently before merge can complete.'
    }
    return 'The lane is in per-track MP4 export. Long export always starts before reel export.'
  }
  if (stage === 'merger') {
    const merge = runtime?.merge ?? row.merge
    if (looksPartialText(merge) || normalizeKey(runtime?.status ?? row.status) === 'partial') {
      return 'Merge is partial — one deliverable branch is ready while the other is still pending.'
    }
    return 'Track-level exports exist and the lane is now focused on producing merged deliverables.'
  }
  if (stage === 'youtube') {
    if (row.meta.youtube_success > 0 || row.meta.youtube_url) {
      return 'YouTube handoff completed for the long merged output.'
    }
    return 'Waiting for YouTube upload — the long merged output is the only valid handoff target.'
  }
  if (stage === 'done') {
    return 'This lane has completed the visible pipeline successfully.'
  }
  if (stage === 'error') {
    return String(runtime?.notes ?? row.notes).trim() || 'This lane needs operator attention in Progress.'
  }
  return 'Select a lane to inspect where it currently sits in the pipeline.'
}

function summaryStat(
  label: string,
  value: number,
  detail: string,
  tone: 'default' | 'active' | 'warning' | 'success' = 'default',
): React.JSX.Element {
  return (
    <div
      className={cn(
        'rounded-2xl border px-4 py-3.5',
        tone === 'warning'
          ? 'border-rose-500/25 bg-rose-500/10'
          : tone === 'active'
            ? 'border-sky-500/25 bg-sky-500/10'
            : tone === 'success'
              ? 'border-emerald-500/25 bg-emerald-500/10'
              : 'border-white/10 bg-slate-950/45',
      )}
    >
      <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold tabular-nums text-white">{value}</p>
      <p className="mt-1 text-xs text-slate-400">{detail}</p>
    </div>
  )
}

function PipelineStrip({ steps }: { steps: WorkflowStep[] }): React.JSX.Element {
  return (
    <div className="overflow-x-auto rounded-2xl border border-white/10 bg-slate-950/40 px-4 py-3.5">
      <div className="flex min-w-[520px] items-center gap-1">
        {steps.map((step, index) => {
          const Icon =
            step.state === 'done'
              ? CheckCircle2
              : step.state === 'running'
                ? LoaderCircle
                : step.state === 'failed'
                  ? XCircle
                  : Circle
          return (
            <div className="flex min-w-0 flex-1 items-center gap-1" key={step.key}>
              <div
                className={cn(
                  'flex min-w-0 flex-1 items-center gap-2 rounded-xl border px-2.5 py-2',
                  step.state === 'running'
                    ? 'border-sky-500/35 bg-sky-500/10'
                    : step.state === 'partial'
                      ? 'border-sky-500/20 bg-sky-500/[0.06]'
                      : step.state === 'done'
                        ? 'border-emerald-500/25 bg-emerald-500/[0.08]'
                        : step.state === 'failed'
                          ? 'border-rose-500/30 bg-rose-500/10'
                          : 'border-transparent bg-transparent',
                )}
              >
                <Icon
                  className={cn(
                    'h-3.5 w-3.5 shrink-0',
                    step.state === 'running' && 'animate-spin text-sky-300',
                    step.state === 'partial' && 'text-sky-300/80',
                    step.state === 'done' && 'text-emerald-300',
                    step.state === 'failed' && 'text-rose-300',
                    step.state === 'inactive' && 'text-slate-500',
                  )}
                />
                <div className="min-w-0">
                  <p className="truncate text-xs font-medium text-slate-100">{step.shortTitle}</p>
                  <p className="truncate text-[10px] uppercase tracking-[0.14em] text-slate-500">
                    {stateLabel(step.state)} · {step.percent}%
                  </p>
                </div>
              </div>
              {index < steps.length - 1 ? (
                <div
                  className={cn(
                    'h-px w-3 shrink-0 sm:w-4',
                    step.state === 'done' ? 'bg-emerald-400/50' : 'bg-white/15',
                  )}
                />
              ) : null}
            </div>
          )
        })}
      </div>
    </div>
  )
}

export function WorkflowPage(): React.JSX.Element {
  const [fromDate, setFromDate] = useState(todayYmd)
  const [toDate, setToDate] = useState(todayYmd)
  const [activeOnly, setActiveOnly] = useState(false)
  const [selectedKey, setSelectedKey] = useState('')

  const filters = useMemo(
    () => ({
      limit: 80,
      activeOnly,
      fromDate,
      toDate,
    }),
    [activeOnly, fromDate, toDate],
  )

  const { data, isLoading, isError, isFetching, refetch } = useProgressRowsQuery(filters)
  const { runtimeByKey } = useProgressVideoRuntime(data?.rows)

  const runtimeRows = useMemo<LaneEntry[]>(
    () =>
      (data?.rows ?? []).map((row) => {
        const key = `${row.meta.batch_id}:${row.meta.profile_id}:${row.meta.role}`
        const runtime = runtimeByKey[key]
        return {
          key,
          row,
          runtime,
          effectiveStage: runtime?.stage ?? row.stage,
          effectiveStatus: runtime?.status ?? row.status,
        }
      }),
    [data?.rows, runtimeByKey],
  )

  useEffect(() => {
    if (!runtimeRows.length) {
      setSelectedKey('')
      return
    }
    if (!runtimeRows.some((entry) => entry.key === selectedKey)) {
      setSelectedKey(runtimeRows[0]!.key)
    }
  }, [runtimeRows, selectedKey])

  const selectedEntry = runtimeRows.find((entry) => entry.key === selectedKey) ?? null
  const selectedRow = selectedEntry?.row ?? null
  const selectedRuntime = selectedEntry?.runtime
  const steps = buildWorkflowSteps(selectedRow, selectedRuntime)
  const selectedStatusLabel = selectedEntry
    ? resolveRunStatusLabel(
        selectedEntry.effectiveStage,
        selectedEntry.effectiveStatus,
        selectedEntry.row,
        selectedRuntime?.converter ?? selectedRow?.converter,
        selectedRuntime?.merge ?? selectedRow?.merge,
      )
    : ''
  const activeCount = useMemo(
    () => runtimeRows.filter((entry) => !['done', 'error'].includes(normalizeKey(entry.effectiveStage))).length,
    [runtimeRows],
  )
  const attentionCount = useMemo(() => runtimeRows.filter((entry) => laneNeedsAttention(entry)).length, [runtimeRows])
  const completedCount = useMemo(
    () => runtimeRows.filter((entry) => normalizeKey(entry.effectiveStage) === 'done').length,
    [runtimeRows],
  )
  const selectedNotes = String(selectedRuntime?.notes ?? selectedRow?.notes ?? '').trim()
  const uploadStatus = selectedRow ? formatUploadStatus(selectedRow) : 'No run selected'

  return (
    <div className="grid gap-5">
      <Card className="p-5">
        <div className="flex flex-wrap items-start gap-3">
          <div className="mr-auto max-w-3xl">
            <p className="text-lg font-semibold text-white">Workflow</p>
            <p className="mt-1 text-sm text-slate-400">
              Visual timeline for one selected run and channel. Use Progress for recovery actions and failed-row handling.
            </p>
            <p className="mt-3 text-xs leading-6 text-slate-500">
              {isLoading
                ? 'Loading workflow runs from the shared progress aggregate feed...'
                : data?.summary ?? 'Ready'}{' '}
              Stage cards stay visual-only; converter and merger reflect desktop runtime when local outputs exist.
            </p>
          </div>

          <div className="flex flex-wrap items-end gap-2.5">
            <DatePickerField className="w-[132px]" label="From" value={fromDate} onChange={setFromDate} />
            <DatePickerField className="w-[132px]" label="To" value={toDate} onChange={setToDate} />
            <InlineToggle className="h-9 px-3 text-[12px]" label="Active only" pressed={activeOnly} onPressedChange={setActiveOnly} />
            <Button className="h-9 gap-2 px-3.5" disabled={isFetching} type="button" variant="secondary" onClick={() => void refetch()}>
              <RefreshCw className={cn('h-4 w-4', isFetching && 'animate-spin')} />
              Refresh
            </Button>
          </div>
        </div>

        <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {summaryStat('Runs', runtimeRows.length, 'Lanes in the current date filter.')}
          {summaryStat('Active', activeCount, 'Still moving through the pipeline.', 'active')}
          {summaryStat(
            'Need Attention',
            attentionCount,
            'Failed, blocked, or pending image/merge blockers.',
            attentionCount > 0 ? 'warning' : 'default',
          )}
          {summaryStat('Done', completedCount, 'Lanes that reached Done.', 'success')}
        </div>
      </Card>

      {isError ? (
        <Card className="border-rose-500/25 bg-rose-500/10 p-6">
          <p className="text-sm font-medium text-rose-100">Workflow data could not be loaded</p>
          <p className="mt-2 text-sm text-rose-200/90">
            Check that the API server is running and the progress aggregate endpoint is available.
          </p>
        </Card>
      ) : null}

      {!runtimeRows.length ? (
        <Card className="p-8">
          <div className="rounded-3xl border border-dashed border-white/10 bg-slate-950/35 px-6 py-14 text-center">
            <p className="text-base font-semibold text-white">{isLoading ? 'Loading workflow runs...' : 'No runs found'}</p>
            <p className="mx-auto mt-3 max-w-md text-sm leading-6 text-slate-400">
              {isLoading
                ? 'Refreshing the visual pipeline board from the shared progress feed.'
                : 'Try widening the date range or turning off Active only to see historical lanes here.'}
            </p>
          </div>
        </Card>
      ) : (
        <div className="grid gap-5 xl:grid-cols-[minmax(260px,300px)_minmax(0,1fr)] xl:items-start">
          <Card className="flex flex-col p-4">
            <div className="border-b border-white/10 pb-3">
              <p className="text-sm font-semibold text-white">Run Lanes</p>
              <p className="mt-1 text-xs leading-5 text-slate-400">
                {runtimeRows.length} lane{runtimeRows.length === 1 ? '' : 's'} · select one for the stage board.
              </p>
            </div>
            <div
              className={cn(
                'mt-3 grid gap-2',
                runtimeRows.length > 6 && 'max-h-[min(68vh,720px)] overflow-y-auto pr-1',
              )}
            >
              {runtimeRows.map((entry) => {
                const selected = entry.key === selectedKey
                const statusLabel = resolveRunStatusLabel(
                  entry.effectiveStage,
                  entry.effectiveStatus,
                  entry.row,
                  entry.runtime?.converter ?? entry.row.converter,
                  entry.runtime?.merge ?? entry.row.merge,
                )
                const needsAttention = laneNeedsAttention(entry)
                return (
                  <button
                    aria-pressed={selected}
                    className={cn(
                      'rounded-xl border px-3.5 py-3 text-left transition',
                      selected
                        ? 'border-sky-500/45 bg-sky-500/[0.12] shadow-[inset_3px_0_0_0_rgba(56,189,248,0.85)]'
                        : needsAttention
                          ? 'border-rose-500/20 bg-rose-500/[0.04] hover:border-rose-500/35'
                          : 'border-white/10 bg-slate-950/40 hover:border-white/20 hover:bg-white/[0.04]',
                    )}
                    key={entry.key}
                    type="button"
                    onClick={() => setSelectedKey(entry.key)}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <p className="truncate text-sm font-medium text-white">{entry.row.channel}</p>
                      <span className="shrink-0 rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] text-slate-300">
                        {formatRoleLabel(entry.row.meta.role)}
                      </span>
                    </div>
                    <p className="mt-1.5 text-[11px] text-slate-500">{entry.row.run_date}</p>
                    <div className="mt-2.5 flex flex-wrap gap-1.5 text-[11px]">
                      <span className={cn('rounded-full border px-2 py-0.5', stageToneClasses(entry.effectiveStage, statusLabel))}>
                        {entry.effectiveStage}
                      </span>
                      <span className={cn('rounded-full border px-2 py-0.5', stageToneClasses(entry.effectiveStage, statusLabel))}>
                        {statusLabel}
                      </span>
                    </div>
                  </button>
                )
              })}
            </div>
          </Card>

          <Card className="overflow-hidden p-0">
            <div className="border-b border-white/10 bg-gradient-to-r from-sky-500/[0.07] via-slate-900/40 to-transparent px-6 py-5">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <p className="text-[11px] uppercase tracking-[0.2em] text-slate-500">Selected Run</p>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <p className="text-xl font-semibold tracking-tight text-white">{selectedRow?.channel ?? 'No run selected'}</p>
                    {selectedRow ? (
                      <>
                        <span className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-[11px] text-slate-200">
                          {formatRoleLabel(selectedRow.meta.role)}
                        </span>
                        <span
                          className={cn(
                            'rounded-full border px-2.5 py-1 text-[11px]',
                            stageToneClasses(selectedRuntime?.stage ?? selectedRow.stage, selectedStatusLabel),
                          )}
                        >
                          {selectedRuntime?.stage ?? selectedRow.stage}
                        </span>
                        <span
                          className={cn(
                            'rounded-full border px-2.5 py-1 text-[11px]',
                            stageToneClasses(selectedRuntime?.stage ?? selectedRow.stage, selectedStatusLabel),
                          )}
                        >
                          {selectedStatusLabel}
                        </span>
                      </>
                    ) : null}
                  </div>
                  <p className="mt-2 text-sm text-slate-400">
                    {selectedRow
                      ? `Run date ${selectedRow.run_date} · Last updated ${selectedRow.updated}`
                      : 'Select a run from the left to see the stage board.'}
                  </p>
                  <p className="mt-3 max-w-4xl text-sm leading-7 text-slate-200">
                    {selectedRow
                      ? buildCurrentFocus(selectedRow, selectedRuntime)
                      : isLoading
                        ? 'Loading workflow details...'
                        : 'Choose a lane to inspect its stage progression and current focus.'}
                  </p>
                </div>
              </div>
            </div>

            <div className="space-y-5 px-6 py-5">
              <div>
                <div className="flex flex-wrap items-end justify-between gap-3">
                  <div>
                    <p className="text-[11px] uppercase tracking-[0.2em] text-slate-500">Stage Board</p>
                    <p className="mt-1.5 text-sm text-slate-300">Pipeline strip plus per-stage progress and readiness.</p>
                  </div>
                </div>

                <div className="mt-4">
                  <PipelineStrip steps={steps} />
                </div>

                <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-5">
                  {steps.map((step) => {
                    const Icon = step.icon
                    const hint = stepEmptyHint(step)
                    const primaryDetail = step.details[0] ?? ''
                    const secondaryDetail = step.details[1] ?? ''
                    const showAwaiting = Boolean(hint) && (detailLooksEmpty(primaryDetail) || step.state === 'inactive')
                    const isSecondary = step.state === 'inactive' || step.state === 'partial'

                    return (
                      <div
                        className={cn(
                          'flex min-h-[168px] flex-col rounded-2xl border p-4',
                          stateClasses(step.state),
                          isSecondary && step.state === 'inactive' && 'shadow-none',
                        )}
                        key={step.key}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="flex min-w-0 items-center gap-2.5">
                            <div className={cn('flex h-9 w-9 shrink-0 items-center justify-center rounded-xl', step.state === 'inactive' ? 'bg-white/5' : 'bg-white/10')}>
                              <Icon className="h-4 w-4" />
                            </div>
                            <div className="min-w-0">
                              <p className="truncate text-sm font-semibold text-inherit">{step.shortTitle}</p>
                              <p className="mt-0.5 truncate text-[11px] text-inherit/70">{step.title}</p>
                            </div>
                          </div>
                          <span className={cn('shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-[0.12em]', stateBadgeClasses(step.state))}>
                            {stateLabel(step.state)}
                          </span>
                        </div>

                        <div className="mt-4">
                          <div className="mb-2 flex items-end justify-between gap-2">
                            <p className="text-xl font-semibold tabular-nums tracking-tight">{step.percent}%</p>
                            <p className="text-xs tabular-nums text-inherit/70">{step.duration}</p>
                          </div>
                          <div className="h-2 overflow-hidden rounded-full bg-black/25">
                            <div
                              className={cn('h-full rounded-full transition-[width] duration-300', progressFillClasses(step.state))}
                              style={{ width: `${step.percent}%` }}
                            />
                          </div>
                        </div>

                        <div className="mt-3 flex flex-1 flex-col justify-end space-y-1.5 text-xs leading-5 text-inherit/85">
                          {showAwaiting ? (
                            <p className="rounded-xl border border-dashed border-white/10 bg-black/15 px-3 py-2 text-inherit/75">
                              {hint}
                            </p>
                          ) : (
                            <>
                              <p className="font-medium">{detailLooksEmpty(primaryDetail) ? (hint ?? 'No detail yet') : primaryDetail}</p>
                              {!detailLooksEmpty(secondaryDetail) && secondaryDetail !== primaryDetail ? (
                                <p className="text-inherit/65">{secondaryDetail}</p>
                              ) : null}
                            </>
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>

              <div className="grid gap-3 border-t border-white/10 pt-4 md:grid-cols-3">
                <div className="min-w-0">
                  <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Notes</p>
                  <p className="mt-2 text-sm leading-6 text-slate-300">
                    {selectedNotes || (selectedRow ? 'No operator notes for this lane.' : isLoading ? 'Loading…' : 'Select a run.')}
                  </p>
                </div>
                <div className="min-w-0">
                  <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Asset Readiness</p>
                  {selectedRow ? (
                    <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-slate-300">
                      <span className={cn('rounded-full border px-2 py-0.5 text-[11px]', selectedRow.meta.long_ready ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-100' : 'border-white/10 bg-white/5 text-slate-400')}>
                        Long {selectedRow.meta.long_ready ? 'ready' : 'waiting'}
                      </span>
                      <span className={cn('rounded-full border px-2 py-0.5 text-[11px]', selectedRow.meta.reel_ready ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-100' : 'border-white/10 bg-white/5 text-slate-400')}>
                        Reel {selectedRow.meta.reel_ready ? 'ready' : 'waiting'}
                      </span>
                    </div>
                  ) : (
                    <p className="mt-2 text-sm text-slate-500">No run selected.</p>
                  )}
                </div>
                <div className="min-w-0">
                  <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Upload</p>
                  {selectedRow ? (
                    <div className="mt-2 space-y-1.5 text-sm text-slate-300">
                      <p className="font-medium">{uploadStatus}</p>
                      <p className="text-xs text-slate-500">
                        {selectedRow.meta.youtube_success > 0 || selectedRow.meta.youtube_url
                          ? `Success ${selectedRow.meta.youtube_success}`
                          : selectedRow.meta.youtube_failed > 0
                            ? `Failed ${selectedRow.meta.youtube_failed}`
                            : selectedRow.meta.youtube_pending > 0
                              ? `Pending ${selectedRow.meta.youtube_pending}`
                              : 'No upload yet'}
                      </p>
                      {selectedRow.meta.youtube_url ? (
                        <p className="break-all text-xs leading-5 text-slate-500">{selectedRow.meta.youtube_url}</p>
                      ) : null}
                    </div>
                  ) : (
                    <p className="mt-2 text-sm text-slate-500">No run selected.</p>
                  )}
                </div>
              </div>
            </div>
          </Card>
        </div>
      )}
    </div>
  )
}
