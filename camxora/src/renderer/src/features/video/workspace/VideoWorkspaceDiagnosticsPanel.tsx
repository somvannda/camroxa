import { Button } from '@/shared/ui/button'
import { SummaryField, WorkspaceBadge } from '@/features/video/workspace/workspaceShellPrimitives'
import type { VideoWorkspaceDiagnosticsState } from '@/features/video/workspace/useVideoWorkspaceDiagnostics'

type VideoWorkspaceDiagnosticsPanelProps = Pick<
  VideoWorkspaceDiagnosticsState,
  | 'backgroundLabel'
  | 'branchLabel'
  | 'canResetLocalDraft'
  | 'dirtyDomains'
  | 'exportStatusLabel'
  | 'exportStatusTone'
  | 'onCopyDiagnostics'
  | 'onRefreshWorkspace'
  | 'onRemountPreview'
  | 'onResetLocalDraft'
  | 'pipelineStatusLabel'
  | 'pipelineStatusTone'
  | 'previewGuidanceDetail'
  | 'previewGuidanceItems'
  | 'previewGuidanceTitle'
  | 'previewGuidanceTone'
  | 'previewNeedsAttention'
  | 'previewStatusLabel'
  | 'previewStatusMessage'
  | 'previewStatusTone'
  | 'saveStatusLabel'
  | 'saveStatusTone'
  | 'templateId'
  | 'trackLabel'
>

export function VideoWorkspaceDiagnosticsPanel({
  backgroundLabel,
  branchLabel,
  canResetLocalDraft,
  dirtyDomains,
  exportStatusLabel,
  exportStatusTone,
  onCopyDiagnostics,
  onRefreshWorkspace,
  onRemountPreview,
  onResetLocalDraft,
  pipelineStatusLabel,
  pipelineStatusTone,
  previewGuidanceDetail,
  previewGuidanceItems,
  previewGuidanceTitle,
  previewGuidanceTone,
  previewNeedsAttention,
  previewStatusLabel,
  previewStatusMessage,
  previewStatusTone,
  saveStatusLabel,
  saveStatusTone,
  templateId,
  trackLabel,
}: VideoWorkspaceDiagnosticsPanelProps): React.JSX.Element {
  const dirtyItems = dirtyDomains.filter((item) => item.dirty)
  const previewGuidanceClassName =
    previewGuidanceTone === 'running'
      ? 'border-fuchsia-400/30 bg-fuchsia-500/10'
      : previewGuidanceTone === 'warning'
        ? 'border-amber-400/30 bg-amber-500/10'
        : 'border-white/10 bg-slate-950/60'

  return (
    <div className="rounded-2xl border border-white/10 bg-[#081028] p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Diagnostics</p>
          <p className="mt-1 text-xs text-slate-400">Recovery and save state for the active workspace.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <WorkspaceBadge label={previewStatusLabel} tone={previewStatusTone} />
          <WorkspaceBadge label={saveStatusLabel} tone={saveStatusTone} />
          {previewNeedsAttention ? <WorkspaceBadge label={exportStatusLabel} tone={exportStatusTone} /> : null}
          {previewNeedsAttention ? <WorkspaceBadge label={pipelineStatusLabel} tone={pipelineStatusTone} /> : null}
        </div>
      </div>

      {dirtyItems.length ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {dirtyItems.map((item) => (
            <WorkspaceBadge key={item.label} label={item.label} tone="warning" />
          ))}
        </div>
      ) : null}

      {previewNeedsAttention ? (
        <div className={`mt-3 rounded-xl border px-3 py-3 text-[11px] text-slate-200 ${previewGuidanceClassName}`}>
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-200">{previewGuidanceTitle}</p>
          <p className="mt-2 leading-5 text-slate-200">{previewGuidanceDetail}</p>
          <ul className="mt-2 space-y-1.5 text-slate-300">
            {previewGuidanceItems.map((item) => (
              <li key={item}>{`\u2022 ${item}`}</li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="mt-3 rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-[11px] leading-5 text-slate-300">
          {previewStatusMessage}
        </p>
      )}

      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        <SummaryField label="Template" value={templateId || 'No template selected'} />
        <SummaryField label="Branch" value={branchLabel} />
        <SummaryField label="Background" value={backgroundLabel} />
        <SummaryField label="Track" value={trackLabel} />
      </div>

      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        <Button className="h-8 px-3 text-xs" size="sm" type="button" variant="secondary" onClick={() => void onRemountPreview()}>
          Remount Preview
        </Button>
        <Button className="h-8 px-3 text-xs" size="sm" type="button" variant="secondary" onClick={() => void onRefreshWorkspace()}>
          Refresh Workspace
        </Button>
        <Button className="h-8 px-3 text-xs" disabled={!canResetLocalDraft} size="sm" type="button" variant="secondary" onClick={onResetLocalDraft}>
          Reset Local Draft
        </Button>
        <Button className="h-8 px-3 text-xs" size="sm" type="button" variant="secondary" onClick={() => void onCopyDiagnostics()}>
          Copy Diagnostics
        </Button>
      </div>
    </div>
  )
}
