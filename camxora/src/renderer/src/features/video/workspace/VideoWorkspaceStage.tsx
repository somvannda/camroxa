import { Pause, Play, SkipBack, SkipForward, Square } from 'lucide-react'

import { RendererVideoPreview } from '@/features/video/RendererVideoPreview'
import type { PreviewLifecycleState } from '@/features/video/preview/previewLifecycleState'
import type { PreviewPlaybackCommand } from '@/features/video/preview/transportClock'
import type { TemplateSettingsDraft } from '@/features/settings/settingsTemplateDraft'
import type { VideoWorkspaceState } from '@/shared/types/desktop'
import { OUTPUT_RESOLUTION_OPTIONS } from '@/shared/lib/outputResolutions'
import { AppSelect } from '@/shared/ui/app-select'
import { Button } from '@/shared/ui/button'
import { Card } from '@/shared/ui/card'
import {
  SummaryField,
  WorkspaceAssetCard,
  WorkspaceBadge,
} from '@/features/video/workspace/workspaceShellPrimitives'

type VideoWorkspaceStageProps = {
  previewTitle: string
  branchLabel: string
  exportReadyLabel: string
  exportReadyTone: 'neutral' | 'ready' | 'warning' | 'running'
  previewStatusLabel: string
  previewStatusTone: 'neutral' | 'ready' | 'warning' | 'running'
  previewGuidanceTitle: string
  previewGuidanceDetail: string
  previewGuidanceItems: string[]
  previewGuidanceTone: 'neutral' | 'ready' | 'warning' | 'running'
  previewNeedsAttention: boolean
  selectedRunLabel: string
  currentTrackLabel: string
  durationLabel: string
  previewAspectStyle: React.CSSProperties
  previewRuntimeNonce: number
  currentBackgroundPath: string
  currentLogoPath: string
  previewTrackPath: string
  selectedTextOverlayIndex: number
  previewTemplate: Record<string, unknown>
  templateDraft: TemplateSettingsDraft | null
  previewPlayback: {
    isPlaying: boolean
    isReady: boolean
    isLoading: boolean
    currentTimeSec: number
    durationSec: number
  }
  previewPlaybackCommand: PreviewPlaybackCommand | null
  enableSpectrumPositionEditing?: boolean
  onPreviewLifecycleStateChange: (state: PreviewLifecycleState) => void
  onSpectrumPositionChange?: (patch: {
    anchor: string
    positionX: number
    positionY: number
    spectrumAttachToLogo: boolean
  }) => void
  onPlaybackStateChange: (state: {
    isPlaying: boolean
    isReady: boolean
    isLoading: boolean
    currentTimeSec: number
    durationSec: number
  }) => void
  workspace: Pick<VideoWorkspaceState, 'previewAspectRatio'>
  issuePreviewPlaybackCommand: (command: { type: 'play' | 'pause' | 'stop' } | { type: 'seek'; timeSec: number }) => void
  saveOutputResolutionPending: boolean
  outputResolution: string
  onOutputResolutionChange: (value: string) => void
  currentBackgroundSourceLabel: string
  currentBackgroundFileName: string
  currentLogoFileName: string
  currentTrackDetail: string
  currentRunDirectory: string
  currentRunDirectoryFileName: string
  onOpenExport: () => void
  onSelectPreviewMp3: () => void | Promise<void>
  onSelectBackground: () => void | Promise<void>
  onEditLogo: () => void
  onEditLayers: () => void
  textSelectionLabel: string
  textSelectionTone: 'neutral' | 'ready'
  renderTextTab: () => React.JSX.Element
}

export function VideoWorkspaceStage({
  previewTitle,
  branchLabel,
  exportReadyLabel,
  exportReadyTone,
  previewStatusLabel,
  previewStatusTone,
  previewGuidanceTitle,
  previewGuidanceDetail,
  previewGuidanceItems,
  previewGuidanceTone,
  previewNeedsAttention,
  selectedRunLabel,
  currentTrackLabel,
  durationLabel,
  previewAspectStyle,
  previewRuntimeNonce,
  currentBackgroundPath,
  currentLogoPath,
  previewTrackPath,
  selectedTextOverlayIndex,
  previewTemplate,
  templateDraft,
  previewPlayback,
  previewPlaybackCommand,
  enableSpectrumPositionEditing,
  onPreviewLifecycleStateChange,
  onSpectrumPositionChange,
  onPlaybackStateChange,
  workspace,
  issuePreviewPlaybackCommand,
  saveOutputResolutionPending,
  outputResolution,
  onOutputResolutionChange,
  currentBackgroundSourceLabel,
  currentBackgroundFileName,
  currentLogoFileName,
  currentTrackDetail,
  currentRunDirectory,
  currentRunDirectoryFileName,
  onOpenExport,
  onSelectPreviewMp3,
  onSelectBackground,
  onEditLogo,
  onEditLayers,
  textSelectionLabel,
  textSelectionTone,
  renderTextTab,
}: VideoWorkspaceStageProps): React.JSX.Element {
  const previewGuidanceClassName =
    previewGuidanceTone === 'running'
      ? 'border-fuchsia-400/30 bg-fuchsia-500/10'
      : previewGuidanceTone === 'warning'
        ? 'border-amber-400/30 bg-amber-500/10'
        : 'border-white/10 bg-[#081028]'

  return (
    <div className="min-h-0 overflow-hidden pr-1">
      <div className="grid h-full min-h-0 gap-4">
        <Card className="flex h-full min-h-0 flex-col overflow-hidden p-0">
          <div className="border-b border-white/10 bg-[linear-gradient(180deg,rgba(17,24,39,0.96),rgba(8,16,40,0.98))] px-4 py-3">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Renderer Preview</p>
                <h2 className="mt-1 text-lg font-semibold text-white">{previewTitle}</h2>
                <p className="mt-1 text-[11px] leading-5 text-slate-400">Preview workspace for the active video.</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <WorkspaceBadge label={branchLabel} />
                <WorkspaceBadge label={previewStatusLabel} tone={previewStatusTone} />
                <WorkspaceBadge label={exportReadyLabel} tone={exportReadyTone} />
              </div>
            </div>
            <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
              <SummaryField label="Run" value={selectedRunLabel} />
              <SummaryField label="Track" value={currentTrackLabel} />
              <SummaryField label="Duration" value={durationLabel} />
            </div>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto p-4">
            <div className="overflow-hidden rounded-3xl border border-white/10 bg-slate-950/50 p-2.5">
              <div
                className="relative flex w-full items-center justify-center overflow-hidden rounded-2xl border border-dashed border-white/10 bg-[radial-gradient(circle_at_top,_rgba(217,70,239,0.18),_transparent_40%),linear-gradient(180deg,rgba(8,16,40,0.95),rgba(3,7,18,1))] text-center shadow-[inset_0_0_0_1px_rgba(255,255,255,0.04)]"
                style={previewAspectStyle}
              >
                <RendererVideoPreview
                  key={`preview-runtime-${previewRuntimeNonce}`}
                  backgroundPath={currentBackgroundPath}
                  logoPath={currentLogoPath}
                  previewVolume={1.35}
                  selectedMp3Path={previewTrackPath}
                  selectedTextOverlayIndex={selectedTextOverlayIndex}
                  template={previewTemplate}
                  templateDraft={templateDraft}
                  playbackCommand={previewPlaybackCommand}
                  enableSpectrumPositionEditing={enableSpectrumPositionEditing}
                  onLifecycleStateChange={onPreviewLifecycleStateChange}
                  onPlaybackStateChange={onPlaybackStateChange}
                  onSpectrumPositionChange={onSpectrumPositionChange}
                  workspace={{
                    playback: previewPlayback,
                    previewAspectRatio: workspace.previewAspectRatio ?? {
                      width: 16,
                      height: 9,
                    },
                  }}
                />
              </div>
            </div>

            <div className="mt-4 rounded-2xl border border-white/10 bg-[#081028] px-3 py-2.5">
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  className="h-8 w-8 shrink-0 px-0"
                  disabled={!previewTrackPath}
                  size="sm"
                  type="button"
                  variant="secondary"
                  onClick={() =>
                    issuePreviewPlaybackCommand({
                      type: 'seek',
                      timeSec: Math.max(0, previewPlayback.currentTimeSec - 5),
                    })
                  }
                >
                  <SkipBack className="h-4 w-4" />
                </Button>
                <Button
                  className="h-8 w-8 shrink-0 px-0"
                  disabled={!previewTrackPath || previewPlayback.isLoading}
                  size="sm"
                  type="button"
                  variant="primary"
                  onClick={() => issuePreviewPlaybackCommand({ type: previewPlayback.isPlaying ? 'pause' : 'play' })}
                >
                  {previewPlayback.isPlaying ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                </Button>
                <Button
                  className="h-8 w-8 shrink-0 px-0"
                  disabled={!previewTrackPath}
                  size="sm"
                  type="button"
                  variant="secondary"
                  onClick={() => issuePreviewPlaybackCommand({ type: 'stop' })}
                >
                  <Square className="h-4 w-4" />
                </Button>
                <Button
                  className="h-8 w-8 shrink-0 px-0"
                  disabled={!previewTrackPath}
                  size="sm"
                  type="button"
                  variant="secondary"
                  onClick={() =>
                    issuePreviewPlaybackCommand({
                      type: 'seek',
                      timeSec: Math.min(
                        previewPlayback.durationSec || previewPlayback.currentTimeSec + 5,
                        previewPlayback.currentTimeSec + 5,
                      ),
                    })
                  }
                >
                  <SkipForward className="h-4 w-4" />
                </Button>
                <span className="shrink-0 text-[11px] text-slate-300">{durationLabel}</span>
                <input
                  className="h-1 min-w-[180px] flex-1 appearance-none rounded-full bg-white/10 accent-fuchsia-500 disabled:cursor-not-allowed"
                  disabled={!previewTrackPath || previewPlayback.durationSec <= 0}
                  max={1000}
                  min={0}
                  type="range"
                  value={
                    previewPlayback.durationSec > 0
                      ? Math.max(
                          0,
                          Math.min(1000, Math.round((previewPlayback.currentTimeSec / previewPlayback.durationSec) * 1000)),
                        )
                      : 0
                  }
                  onChange={(event) => {
                    if (previewPlayback.durationSec <= 0) {
                      return
                    }
                    const ratio = Number(event.target.value) / 1000
                    issuePreviewPlaybackCommand({
                      type: 'seek',
                      timeSec: previewPlayback.durationSec * ratio,
                    })
                  }}
                />
                <div className="min-w-[220px] flex-1 xl:max-w-[240px]">
                  <AppSelect
                    disabled={saveOutputResolutionPending}
                    options={OUTPUT_RESOLUTION_OPTIONS}
                    placeholder="Output resolution"
                    triggerClassName="h-8 bg-slate-950/70 text-[11px]"
                    value={outputResolution}
                    onChange={(value) => onOutputResolutionChange(String(value || ''))}
                  />
                </div>
              </div>
            </div>

            {previewNeedsAttention ? (
              <div className={`mt-4 rounded-2xl border px-3 py-3 ${previewGuidanceClassName}`}>
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Preview Guidance</p>
                    <p className="mt-1 text-sm font-medium text-white">{previewGuidanceTitle}</p>
                  </div>
                </div>
                <p className="mt-2 text-xs leading-5 text-slate-200">{previewGuidanceDetail}</p>
                <ul className="mt-3 grid gap-2 text-[11px] leading-5 text-slate-300 md:grid-cols-2">
                  {previewGuidanceItems.map((item) => (
                    <li key={item} className="rounded-xl border border-white/10 bg-slate-950/40 px-3 py-2">
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            <div className="mt-4 rounded-2xl border border-white/10 bg-[#081028] p-3">
              <div className="flex justify-end">
                <Button className="h-8 px-3 text-xs" size="sm" type="button" variant="secondary" onClick={onOpenExport}>
                  Export Queue
                </Button>
              </div>
              <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-4">
                <WorkspaceAssetCard
                  detail={currentBackgroundPath ? `${currentBackgroundSourceLabel} · ${currentBackgroundPath}` : currentBackgroundSourceLabel}
                  label="Background"
                  tone={currentBackgroundPath ? 'ready' : 'warning'}
                  value={currentBackgroundFileName}
                />
                <WorkspaceAssetCard
                  detail={currentLogoPath || 'Select a logo in the Logo tab'}
                  label="Logo"
                  tone={currentLogoPath ? 'ready' : 'warning'}
                  value={currentLogoFileName}
                />
                <WorkspaceAssetCard
                  detail={currentTrackDetail}
                  label="Track"
                  tone={previewTrackPath ? 'ready' : 'warning'}
                  value={currentTrackLabel}
                />
                <WorkspaceAssetCard
                  detail={currentRunDirectory || 'No resolved run directory'}
                  label="Run Directory"
                  tone={currentRunDirectory ? 'ready' : 'warning'}
                  value={currentRunDirectoryFileName}
                />
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <Button className="h-8 px-3 text-xs" size="sm" type="button" variant="secondary" onClick={() => void onSelectPreviewMp3()}>
                  Select MP3
                </Button>
                <Button className="h-8 px-3 text-xs" size="sm" type="button" variant="secondary" onClick={() => void onSelectBackground()}>
                  Background
                </Button>
                <Button className="h-8 px-3 text-xs" size="sm" type="button" variant="secondary" onClick={onEditLogo}>
                  Edit Logo
                </Button>
                <Button className="h-8 px-3 text-xs" size="sm" type="button" variant="secondary" onClick={onEditLayers}>
                  Layers
                </Button>
              </div>
            </div>

            <div className="mt-4 rounded-2xl border border-white/10 bg-[#081028] p-3">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Text Layers</p>
                  <p className="mt-1 text-xs text-slate-400">Manage on-canvas text directly under the preview stage.</p>
                </div>
                <WorkspaceBadge label={textSelectionLabel} tone={textSelectionTone} />
              </div>
              <div className="mt-3">{renderTextTab()}</div>
            </div>
          </div>
        </Card>
      </div>
    </div>
  )
}
