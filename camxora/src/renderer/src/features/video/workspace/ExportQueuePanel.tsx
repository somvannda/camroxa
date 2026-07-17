import { Button } from '@/shared/ui/button'
import { AppSelect } from '@/shared/ui/app-select'
import { InlineToggle } from '@/shared/ui/inline-toggle'
import type { VideoExportState } from '@/shared/types/desktop'
import type { ProgressRowResponse } from '@/shared/api/platformEndpoints'
import type { VideoPipelineBranch } from '@/shared/lib/videoPipelineInputs'
import { cn } from '@/shared/lib/utils'
import { SelectField } from '@/features/video/workspace/inspectorFields'

const EXPORT_SPEED_OPTIONS: ReadonlyArray<{ label: string; value: string }> = [
  { label: 'Balanced', value: 'balanced' },
  { label: 'Fast', value: 'fast' },
  { label: 'Very Fast', value: 'very_fast' },
]

const EXPORT_WORKER_OPTIONS: ReadonlyArray<{ label: string; value: string }> = Array.from({ length: 10 }, (_, index) => ({
  label: String(index + 1),
  value: String(index + 1),
}))

function formatDurationLabel(totalSeconds: number): string {
  const seconds = Math.max(0, Math.round(Number(totalSeconds) || 0))
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const remainingSeconds = seconds % 60

  if (hours > 0) {
    return `${hours}h ${minutes}m`
  }
  if (minutes > 0) {
    return `${minutes}m ${remainingSeconds}s`
  }
  return `${remainingSeconds}s`
}

function SummaryField(props: { label: string; value: string }): React.JSX.Element {
  return (
    <div className="rounded-xl border border-white/10 bg-[#081028] px-2.5 py-2">
      <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">{props.label}</p>
      <p className="mt-0.5 text-xs font-medium text-slate-100">{props.value}</p>
    </div>
  )
}

type Mp3ListItem = { name: string; path: string }

type ExportQueuePanelProps = {
  mp3List: Mp3ListItem[]
  selectedMp3Path: string
  isProgressLoading: boolean
  pipelineRows: ProgressRowResponse[]
  selectedPipelineRunKey: string
  buildVideoPipelineRunKey: (row: ProgressRowResponse) => string
  setSelectedPipelineRunKey: (value: string) => void
  selectedPipelineBranch: VideoPipelineBranch
  setSelectedPipelineBranch: (value: VideoPipelineBranch) => void
  onApplyPreviewMp3Selection: (path: string) => Promise<unknown> | void
  onSelectAndPlayPreviewMp3: (path: string) => Promise<unknown> | void
  onHandleSelectPreviewMp3: () => Promise<unknown> | void
  onOpenExportOutputFile: () => Promise<unknown> | void
  onOpenExportOutputFolder: () => Promise<unknown> | void
  exportState: Partial<VideoExportState>
  selectedPipelineRow: ProgressRowResponse | null
  resolvedPipelineInputs: {
    ready: boolean
    backgroundPath?: string | null
    thumbnailPath?: string | null
    runDir?: string | null
    sourceMode?: string | null
  }
  startPipelineExportPending: boolean
  startManualExportPending: boolean
  stopPipelineExportPending: boolean
  onStartManualExport: () => Promise<unknown> | void
  onStartExport: () => Promise<unknown> | void
  onStopExport: () => Promise<unknown> | void
  formatPath: (value: string) => string
}

export function ExportQueuePanel({
  mp3List,
  selectedMp3Path,
  isProgressLoading,
  pipelineRows,
  selectedPipelineRunKey,
  buildVideoPipelineRunKey,
  setSelectedPipelineRunKey,
  selectedPipelineBranch,
  setSelectedPipelineBranch,
  onApplyPreviewMp3Selection,
  onSelectAndPlayPreviewMp3,
  onHandleSelectPreviewMp3,
  onOpenExportOutputFile,
  onOpenExportOutputFolder,
  exportState,
  selectedPipelineRow,
  resolvedPipelineInputs,
  startPipelineExportPending,
  startManualExportPending,
  stopPipelineExportPending,
  onStartManualExport,
  onStartExport,
  onStopExport,
  formatPath,
}: ExportQueuePanelProps): React.JSX.Element {
  const completedJobs = Math.max(0, Number(exportState.completedJobs ?? 0))
  const totalJobs = Math.max(0, Number(exportState.totalJobs ?? 0))
  const progressPercent =
    typeof exportState.progressPercent === 'number' && Number.isFinite(exportState.progressPercent)
      ? Math.max(0, Math.min(100, exportState.progressPercent))
      : totalJobs > 0
        ? Math.max(0, Math.min(100, (completedJobs / totalJobs) * 100))
        : 0
  const progressPercentLabel = `${Math.round(progressPercent)}%`
  const currentOutputPath = String(exportState.currentOutputPath ?? '').trim()
  const lastOutputPath = String(exportState.lastOutputPath ?? '').trim()
  const hasOpenableOutputFile = Boolean(currentOutputPath || lastOutputPath)
  const hasOpenableOutputFolder = Boolean(String(exportState.outputDir ?? '').trim() || currentOutputPath || lastOutputPath)
  const etaLabel =
    exportState.running && typeof exportState.estimatedRemainingSec === 'number'
      ? `ETA ${formatDurationLabel(exportState.estimatedRemainingSec)}`
      : exportState.running
        ? 'ETA estimating...'
        : totalJobs > 0 && completedJobs >= totalJobs
          ? 'Completed'
          : 'Idle'

  return (
    <div className="grid gap-3">
      <div className="rounded-2xl border border-white/10 bg-slate-950/40 p-2.5">
        <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Track list</p>
        {mp3List.length ? (
          <div className="mt-2.5 max-h-[220px] space-y-1.5 overflow-y-auto pr-1">
            {mp3List.map((item) => (
              <button
                className={cn(
                  'w-full rounded-xl border px-2.5 py-1.5 text-left text-xs transition-colors',
                  item.path === selectedMp3Path
                    ? 'border-fuchsia-500/40 bg-fuchsia-500/10 text-white'
                    : 'border-white/10 bg-[#081028] text-slate-300 hover:border-white/20 hover:bg-white/5',
                )}
                key={item.path}
                type="button"
                onClick={() => {
                  void onApplyPreviewMp3Selection(item.path)
                }}
                onDoubleClick={() => {
                  void onSelectAndPlayPreviewMp3(item.path)
                }}
              >
                {item.name}
              </button>
            ))}
          </div>
        ) : (
          <div className="mt-2.5 rounded-xl border border-dashed border-white/10 bg-[#081028] px-3 py-5 text-xs text-slate-400">
            No preview music is attached yet.
          </div>
        )}
      </div>

      <div className="rounded-2xl border border-white/10 bg-slate-950/40 p-2.5">
        <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Actions</p>
        <div className="mt-3 grid gap-2.5">
          <SelectField
            label="Pipeline run"
            disabled={isProgressLoading || !pipelineRows.length}
            placeholder="No pipeline runs with resolved assets yet"
            value={selectedPipelineRunKey}
            options={
              pipelineRows.length
                ? pipelineRows.map((row) => ({
                    label: `${row.channel} · ${row.run_date} · ${String(row.meta.role).toUpperCase()}`,
                    value: buildVideoPipelineRunKey(row),
                  }))
                : []
            }
            onChange={setSelectedPipelineRunKey}
          />
          <SelectField
            label="Branch"
            value={selectedPipelineBranch}
            options={[
              { label: 'Long (16:9)', value: 'long' },
              { label: 'Reel (9:16)', value: 'reel' },
            ]}
            onChange={(value) => setSelectedPipelineBranch((value || 'long') as VideoPipelineBranch)}
          />
        </div>
        <div className="mt-3 grid gap-2">
          <Button size="sm" type="button" variant="secondary" onClick={() => void onHandleSelectPreviewMp3()}>
            Select MP3
          </Button>
          <Button
            disabled={!hasOpenableOutputFolder}
            size="sm"
            type="button"
            variant="secondary"
            onClick={() => void onOpenExportOutputFolder()}
          >
            Open Output Folder
          </Button>
          <Button
            disabled={!hasOpenableOutputFile}
            size="sm"
            type="button"
            variant="secondary"
            onClick={() => void onOpenExportOutputFile()}
          >
            Open Output File
          </Button>
          <Button
            disabled={
              exportState.running ||
              !selectedMp3Path ||
              startManualExportPending ||
              startPipelineExportPending ||
              stopPipelineExportPending
            }
            size="sm"
            type="button"
            variant="primary"
            onClick={() => void onStartManualExport()}
          >
            {startManualExportPending ? 'Starting Manual Export...' : 'Manual Export'}
          </Button>
          <Button disabled size="sm" type="button" variant="secondary">
            Generate Thumbnail
          </Button>
          <Button
            disabled={
              exportState.running
                ? stopPipelineExportPending
                : !selectedPipelineRow ||
                  !resolvedPipelineInputs.ready ||
                  !resolvedPipelineInputs.backgroundPath ||
                  startPipelineExportPending ||
                  stopPipelineExportPending
            }
            size="sm"
            type="button"
            variant={exportState.running ? 'secondary' : 'primary'}
            onClick={() => (exportState.running ? void onStopExport() : void onStartExport())}
          >
            {startPipelineExportPending
              ? 'Starting Export...'
              : stopPipelineExportPending
                ? 'Stopping...'
                : exportState.running
                  ? 'Stop Export'
                  : 'Export'}
          </Button>
        </div>
        <div className="mt-3 grid grid-cols-3 gap-2">
          <div className="rounded-xl border border-white/10 bg-white/5 px-2.5 py-2">
            <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Auto merge</p>
            <InlineToggle
              className="mt-1 w-full justify-center"
              disabled
              label="Auto merge MP4"
              pressed={Boolean(exportState.autoMerge)}
              showLabel={false}
              onPressedChange={() => undefined}
            />
          </div>
          <div className="rounded-xl border border-white/10 bg-white/5 px-2.5 py-2">
            <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Speed</p>
            <AppSelect
              disabled
              options={EXPORT_SPEED_OPTIONS}
              placeholder="Speed"
              triggerClassName="mt-1 h-8 bg-slate-950/70 text-[11px]"
              value="balanced"
              onChange={() => undefined}
            />
          </div>
          <div className="rounded-xl border border-white/10 bg-white/5 px-2.5 py-2">
            <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Workers</p>
            <AppSelect
              disabled
              options={EXPORT_WORKER_OPTIONS}
              placeholder="Workers"
              triggerClassName="mt-1 h-8 bg-slate-950/70 text-[11px]"
              value={String(Math.max(1, Number(exportState.workers ?? 1)))}
              onChange={() => undefined}
            />
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-white/10 bg-slate-950/40 p-2.5">
        <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Status</p>
        <div className="mt-3 space-y-3">
          <div>
            <div className="mb-2 flex items-center justify-between gap-3">
              <p className="text-xs font-medium text-white">Overall</p>
              <span className="text-xs text-slate-400">
                {completedJobs}/{totalJobs} · {progressPercentLabel}
              </span>
            </div>
            <div className="h-1.5 rounded-full bg-white/10">
              <div
                className="h-1.5 rounded-full bg-fuchsia-500/70"
                style={{
                  width: `${progressPercent}%`,
                }}
              />
            </div>
            <div className="mt-2 flex items-center justify-between gap-3 text-[11px] text-slate-400">
              <span>Progress {progressPercentLabel}</span>
              <span>{etaLabel}</span>
            </div>
          </div>
          <div>
            <div className="mb-2 flex items-center justify-between gap-3">
              <p className="text-xs font-medium text-white">Merge</p>
              <span className="text-xs text-slate-400">
                {exportState.mergeRunning ? 'Running' : exportState.autoMerge ? 'Enabled' : 'Idle'}
              </span>
            </div>
            <div className="h-1.5 rounded-full bg-white/10">
              <div
                className={cn('h-1.5 rounded-full', exportState.mergeRunning ? 'bg-emerald-500/70' : 'bg-white/15')}
                style={{ width: exportState.mergeRunning ? '50%' : exportState.lastMergedOutputPath ? '100%' : '0%' }}
              />
            </div>
            {exportState.mergeRunning ? (
              <Button className="mt-2 w-full" disabled size="sm" type="button" variant="secondary">
                Stop Merge
              </Button>
            ) : null}
          </div>
          <div className="grid gap-2 md:grid-cols-3">
            <SummaryField
              label="Branch"
              value={
                pipelineRows.length
                  ? resolvedPipelineInputs.ready
                    ? `${selectedPipelineBranch === 'long' ? 'Long' : 'Reel'} ready`
                    : `${selectedPipelineBranch === 'long' ? 'Long' : 'Reel'} missing assets`
                  : 'No run selected'
              }
            />
            <SummaryField
              label="Current track"
              value={selectedMp3Path ? selectedMp3Path.split(/[\\/]/).pop() || selectedMp3Path : 'No track selected'}
            />
            <SummaryField
              label="Source mode"
              value={resolvedPipelineInputs.sourceMode ? resolvedPipelineInputs.sourceMode.toUpperCase() : '--'}
            />
          </div>
          <div className="rounded-xl border border-white/10 bg-[#081028] p-2.5 text-xs text-slate-300">
            <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Details</p>
            <p className="mt-1 font-medium text-white">{exportState.currentStatus ?? 'Unavailable'}</p>
            <p className="mt-2 break-all text-[10px] text-slate-500">Run directory: {formatPath(resolvedPipelineInputs.runDir ?? '')}</p>
            <p className="mt-1.5 break-all text-[10px] text-slate-500">
              Resolved background: {formatPath(resolvedPipelineInputs.backgroundPath ?? '')}
            </p>
            <p className="mt-1.5 break-all text-[10px] text-slate-500">
              Resolved thumbnail: {formatPath(resolvedPipelineInputs.thumbnailPath ?? '')}
            </p>
            <p className="mt-1.5 break-all text-[10px] text-slate-500">Output folder: {formatPath(exportState.outputDir ?? '')}</p>
            <p className="mt-1.5 break-all text-[10px] text-slate-500">Target output: {formatPath(currentOutputPath)}</p>
            <p className="mt-1.5 break-all text-[10px] text-slate-500">Last output: {formatPath(lastOutputPath)}</p>
            <p className="mt-1.5 break-all text-[10px] text-slate-500">
              Last merged output: {formatPath(exportState.lastMergedOutputPath ?? '')}
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
