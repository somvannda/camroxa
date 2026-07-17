import type { PreviewPlaybackCommand } from '@/features/video/preview/transportClock'
import type { TemplateSettingsDraft, TemplateTextOverlayDraft } from '@/features/settings/settingsTemplateDraft'
import { BackgroundInspector } from '@/features/video/workspace/BackgroundInspector'
import { VideoWorkspaceDiagnosticsPanel } from '@/features/video/workspace/VideoWorkspaceDiagnosticsPanel'
import { ExportQueuePanel } from '@/features/video/workspace/ExportQueuePanel'
import { LogoInspector } from '@/features/video/workspace/LogoInspector'
import { ParticlesInspector } from '@/features/video/workspace/ParticlesInspector'
import { SpectrumInspector } from '@/features/video/workspace/SpectrumInspector'
import {
  SpectrumLayerEditor,
  buildSpectrumLayerInspectorState,
} from '@/features/video/workspace/SpectrumLayerEditor'
import { TextLayerListPanel } from '@/features/video/workspace/TextPanels'
import type { VideoWorkspaceDraftDirtyState, VideoWorkspaceDraftSlices } from '@/features/video/workspace/templateDraftDomains'
import type { PreviewPlaybackState, VideoTabId } from '@/features/video/workspace/useVideoWorkspaceShell'
import { VideoWorkspaceLeftRail } from '@/features/video/workspace/VideoWorkspaceLeftRail'
import { VideoWorkspaceRightRail } from '@/features/video/workspace/VideoWorkspaceRightRail'
import { VideoWorkspaceStage } from '@/features/video/workspace/VideoWorkspaceStage'
import { buildVideoPipelineRunKey, type VideoPipelineBranch } from '@/shared/lib/videoPipelineInputs'
import type { VideoWorkspaceState } from '@/shared/types/desktop'
import type { ProgressRowResponse } from '@/shared/api/platformEndpoints'
import type { CompactTabOption } from '@/shared/ui/compact-tabs'
import type { EffectPackSelectionStatus } from '@shared/effectPacks/effectPackContracts'
import type { PreviewLifecycleState } from '@/features/video/preview/previewLifecycleState'
import type { VideoWorkspaceDiagnosticsState } from '@/features/video/workspace/useVideoWorkspaceDiagnostics'

function formatPath(value: string): string {
  return value.trim() || 'Not selected'
}

function formatSeconds(value: number): string {
  if (!Number.isFinite(value) || value <= 0) {
    return '00:00'
  }
  const minutes = Math.floor(value / 60)
  const seconds = Math.floor(value % 60)
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
}

function getFileName(value: string): string {
  const trimmed = String(value || '').trim()
  if (!trimmed) {
    return 'Not selected'
  }
  return trimmed.split(/[\\/]/).pop() || trimmed
}

export type VideoWorkspaceShellProps = {
  workspace: VideoWorkspaceState | undefined
  isLoading: boolean
  activeTab: VideoTabId
  backgroundPathDraft: string
  diagnosticsState: VideoWorkspaceDiagnosticsState
  draftDirtyState: VideoWorkspaceDraftDirtyState
  draftSlices: VideoWorkspaceDraftSlices | null
  deleteTemplatePending: boolean
  editableSpectrumLayers: Record<string, unknown>[]
  layerOptions: Array<{ label: string; value: string }>
  patchTemplatePending: boolean
  previewAspectStyle: React.CSSProperties
  previewPlayback: PreviewPlaybackState
  previewPlaybackCommand: PreviewPlaybackCommand | null
  previewTemplate: Record<string, unknown>
  previewTrackPath: string
  saveOutputResolutionPending: boolean
  saveTemplatePending: boolean
  selectedLayerIndex: number | undefined
  selectedLayerKey: string
  selectedLayerRecord: Record<string, unknown> | null
  selectedPipelineBranch: VideoPipelineBranch
  selectedPipelineRow: ProgressRowResponse | null
  selectedTemplateId: string
  selectedTextOverlay: TemplateTextOverlayDraft | null
  selectedTextOverlayIndex: number
  settingsTabs: ReadonlyArray<CompactTabOption>
  sidePanelTab: 'text' | 'animation' | 'export'
  spectrumEffectPackOptions: Array<{ label: string; value: string }>
  spectrumEffectPackSelectionValue: string
  spectrumEffectPackStatus: EffectPackSelectionStatus
  backgroundEffectPackOptions: Array<{ label: string; value: string }>
  backgroundEffectPackSelectionValue: string
  backgroundEffectPackStatus: EffectPackSelectionStatus
  logoEffectPackOptions: Array<{ label: string; value: string }>
  logoEffectPackSelectionValue: string
  logoEffectPackStatus: EffectPackSelectionStatus
  particlesEffectPackOptions: Array<{ label: string; value: string }>
  particlesEffectPackSelectionValue: string
  particlesEffectPackStatus: EffectPackSelectionStatus
  effectPackBusy: boolean
  startManualExportPending: boolean
  startPipelineExportPending: boolean
  stopPipelineExportPending: boolean
  templateDraft: TemplateSettingsDraft | null
  templateNameDraft: string
  workspaceDirty: boolean
  textOverlays: TemplateTextOverlayDraft[]
  textPanelMode: 'basic' | 'style' | 'effects'
  textPresetId: string
  pipelineRows: ProgressRowResponse[]
  progressIsLoading: boolean
  resolvedPipelineInputs: {
    ready: boolean
    backgroundPath?: string | null
    thumbnailPath?: string | null
    runDir?: string | null
    sourceMode?: string | null
  }
  templates: ReadonlyArray<{ id: string; name: string }>
  onActiveTabChange: (value: VideoTabId) => void
  onAddLayer: () => void
  onAddTextOverlay: () => void
  onApplyLogoShape: (value: string) => void
  onApplyLogoSize: (value: number) => void
  onApplyPreviewMp3Selection: (path: string) => Promise<unknown> | void
  onApplyBackgroundEffectPack: (value: string) => void
  onApplyLogoEffectPack: (value: string) => void
  onApplyParticlesEffectPack: (value: string) => void
  onApplySpectrumEffectPack: (value: string) => void
  onApplySpectrumPreset: (preset: string) => void
  onApplyTextAnchorAlignment: (alignment: 'left' | 'center' | 'right') => void
  onApplyTextCase: (mode: 'upper' | 'lower' | 'title') => void
  onApplyTextPreset: (preset: string) => void
  onDeleteLayer: () => void
  onDeleteTemplate: () => void | Promise<void>
  onDeleteTextOverlay: () => void
  onDuplicateLayer: () => void
  onDuplicateTextOverlay: () => void
  onFlushSpectrumLayerCommit: () => void
  onHandleSelectBackground: () => Promise<unknown> | void
  onHandlePreviewLifecycleStateChange: (state: PreviewLifecycleState) => void
  onHandleSelectPreviewMp3: () => Promise<unknown> | void
  onHandleTemplateSelectionChange: (value: string) => void
  onInstallEffectPack: () => void | Promise<void>
  onIssuePreviewPlaybackCommand: (command: { type: 'play' | 'pause' | 'stop' } | { type: 'seek'; timeSec: number }) => void
  onMoveTextOverlay: (direction: -1 | 1) => void
  onPatchBackgroundDraft: (patch: Partial<VideoWorkspaceDraftSlices['background']>) => void
  onPatchLayer: (patch: Record<string, unknown>, deferPersistence?: boolean) => void
  onPatchLayerColor: (patch: Record<string, unknown>, deferPersistence?: boolean) => void
  onPatchLogoDraft: (patch: Partial<VideoWorkspaceDraftSlices['logo']>) => void
  onPatchParticlesDraft: (patch: Partial<VideoWorkspaceDraftSlices['particles']>) => void
  onPatchSpectrumDraft: (patch: Partial<VideoWorkspaceDraftSlices['spectrum']>) => void
  onResetBackgroundTransform: () => void
  onReloadEffectPacks: () => void | Promise<unknown>
  onSaveOutputResolution: (value: string) => void
  onSaveTemplate: () => void | Promise<void>
  onSelectAndPlayPreviewMp3: (path: string) => Promise<unknown> | void
  onOpenExportOutputFile: () => Promise<unknown> | void
  onOpenExportOutputFolder: () => Promise<unknown> | void
  onSelectLayer: (value: string) => void
  onSelectLogo: () => void | Promise<void>
  onSetPreviewPlayback: (state: PreviewPlaybackState) => void
  onSetSelectedPipelineBranch: (value: VideoPipelineBranch) => void
  onSetSelectedPipelineRunKey: (value: string) => void
  onSetSelectedTextOverlayKey: (key: string) => void
  onSetSidePanelTab: (tab: 'text' | 'animation' | 'export') => void
  onSetSpectrumLogoGap: (value: number) => void
  onSetTemplateNameDraft: (value: string) => void
  onSetTextPanelMode: (mode: 'basic' | 'style' | 'effects') => void
  onSetTextPresetId: (value: string) => void
  onStartManualExport: () => Promise<unknown> | void
  onStartPipelineExport: () => Promise<unknown> | void
  onStopPipelineExport: () => Promise<unknown> | void
  onToggleSpectrumAttachment: (value: boolean) => void
  onToggleBackgroundEffectPackEnabled: () => void | Promise<void>
  onToggleLogoEffectPackEnabled: () => void | Promise<void>
  onToggleParticlesEffectPackEnabled: () => void | Promise<void>
  onToggleSpectrumEffectPackEnabled: () => void | Promise<void>
  onUpdateTextOverlay: (index: number, nextOverlay: TemplateTextOverlayDraft) => void
  onActivateBackgroundEffectPackVersion: () => void | Promise<void>
  onActivateLogoEffectPackVersion: () => void | Promise<void>
  onActivateParticlesEffectPackVersion: () => void | Promise<void>
  onActivateSpectrumEffectPackVersion: () => void | Promise<void>
  onClearBackgroundEffectPack: () => void
  onClearLogoEffectPack: () => void
  onClearParticlesEffectPack: () => void
  onClearSpectrumEffectPack: () => void
  onRemoveBackgroundEffectPackVersion: () => void | Promise<void>
  onRemoveLogoEffectPackVersion: () => void | Promise<void>
  onRemoveParticlesEffectPackVersion: () => void | Promise<void>
  onRemoveSpectrumEffectPackVersion: () => void | Promise<void>
  getTextAnchorAlignment: (anchor: string) => 'left' | 'center' | 'right'
}

export function VideoWorkspaceShell({
  workspace,
  isLoading,
  activeTab,
  backgroundPathDraft,
  diagnosticsState,
  draftDirtyState,
  draftSlices,
  deleteTemplatePending,
  editableSpectrumLayers,
  layerOptions,
  patchTemplatePending,
  previewAspectStyle,
  previewPlayback,
  previewPlaybackCommand,
  previewTemplate,
  previewTrackPath,
  saveOutputResolutionPending,
  saveTemplatePending,
  selectedLayerIndex,
  selectedLayerKey,
  selectedLayerRecord,
  selectedPipelineBranch,
  selectedPipelineRow,
  selectedTemplateId,
  selectedTextOverlay,
  selectedTextOverlayIndex,
  settingsTabs,
  sidePanelTab,
  spectrumEffectPackOptions: _spectrumEffectPackOptions,
  spectrumEffectPackSelectionValue: _spectrumEffectPackSelectionValue,
  spectrumEffectPackStatus: _spectrumEffectPackStatus,
  backgroundEffectPackOptions: _backgroundEffectPackOptions,
  backgroundEffectPackSelectionValue: _backgroundEffectPackSelectionValue,
  backgroundEffectPackStatus: _backgroundEffectPackStatus,
  logoEffectPackOptions: _logoEffectPackOptions,
  logoEffectPackSelectionValue: _logoEffectPackSelectionValue,
  logoEffectPackStatus: _logoEffectPackStatus,
  particlesEffectPackOptions: _particlesEffectPackOptions,
  particlesEffectPackSelectionValue: _particlesEffectPackSelectionValue,
  particlesEffectPackStatus: _particlesEffectPackStatus,
  effectPackBusy: _effectPackBusy,
  startManualExportPending,
  startPipelineExportPending,
  stopPipelineExportPending,
  templateDraft,
  templateNameDraft,
  workspaceDirty,
  textOverlays,
  textPanelMode,
  textPresetId,
  pipelineRows,
  progressIsLoading,
  resolvedPipelineInputs,
  templates,
  onActiveTabChange,
  onAddLayer,
  onAddTextOverlay,
  onApplyLogoShape,
  onApplyLogoSize,
  onApplyPreviewMp3Selection,
  onApplyBackgroundEffectPack: _onApplyBackgroundEffectPack,
  onApplyLogoEffectPack: _onApplyLogoEffectPack,
  onApplyParticlesEffectPack: _onApplyParticlesEffectPack,
  onApplySpectrumEffectPack: _onApplySpectrumEffectPack,
  onApplySpectrumPreset,
  onApplyTextAnchorAlignment,
  onApplyTextCase,
  onApplyTextPreset,
  onDeleteLayer,
  onDeleteTemplate,
  onDeleteTextOverlay,
  onDuplicateLayer,
  onDuplicateTextOverlay,
  onFlushSpectrumLayerCommit,
  onHandleSelectBackground,
  onHandlePreviewLifecycleStateChange,
  onHandleSelectPreviewMp3,
  onHandleTemplateSelectionChange,
  onInstallEffectPack: _onInstallEffectPack,
  onIssuePreviewPlaybackCommand,
  onMoveTextOverlay,
  onPatchBackgroundDraft,
  onPatchLayer,
  onPatchLayerColor,
  onPatchLogoDraft,
  onPatchParticlesDraft,
  onPatchSpectrumDraft,
  onResetBackgroundTransform,
  onReloadEffectPacks: _onReloadEffectPacks,
  onSaveOutputResolution,
  onSaveTemplate,
  onSelectAndPlayPreviewMp3,
  onOpenExportOutputFile,
  onOpenExportOutputFolder,
  onSelectLayer,
  onSelectLogo,
  onSetPreviewPlayback,
  onSetSelectedPipelineBranch,
  onSetSelectedPipelineRunKey,
  onSetSelectedTextOverlayKey,
  onSetSidePanelTab,
  onSetSpectrumLogoGap,
  onSetTemplateNameDraft,
  onSetTextPanelMode,
  onSetTextPresetId,
  onStartManualExport,
  onStartPipelineExport,
  onStopPipelineExport,
  onToggleSpectrumAttachment,
  onToggleBackgroundEffectPackEnabled: _onToggleBackgroundEffectPackEnabled,
  onToggleLogoEffectPackEnabled: _onToggleLogoEffectPackEnabled,
  onToggleParticlesEffectPackEnabled: _onToggleParticlesEffectPackEnabled,
  onToggleSpectrumEffectPackEnabled: _onToggleSpectrumEffectPackEnabled,
  onUpdateTextOverlay,
  onActivateBackgroundEffectPackVersion: _onActivateBackgroundEffectPackVersion,
  onActivateLogoEffectPackVersion: _onActivateLogoEffectPackVersion,
  onActivateParticlesEffectPackVersion: _onActivateParticlesEffectPackVersion,
  onActivateSpectrumEffectPackVersion: _onActivateSpectrumEffectPackVersion,
  onClearBackgroundEffectPack: _onClearBackgroundEffectPack,
  onClearLogoEffectPack: _onClearLogoEffectPack,
  onClearParticlesEffectPack: _onClearParticlesEffectPack,
  onClearSpectrumEffectPack: _onClearSpectrumEffectPack,
  onRemoveBackgroundEffectPackVersion: _onRemoveBackgroundEffectPackVersion,
  onRemoveLogoEffectPackVersion: _onRemoveLogoEffectPackVersion,
  onRemoveParticlesEffectPackVersion: _onRemoveParticlesEffectPackVersion,
  onRemoveSpectrumEffectPackVersion: _onRemoveSpectrumEffectPackVersion,
  getTextAnchorAlignment,
}: VideoWorkspaceShellProps): React.JSX.Element {
  const selectedLayerInspectorState = buildSpectrumLayerInspectorState(selectedLayerIndex, selectedLayerRecord)

  const renderSpectrumLayersCard = () => {
    return (
      <SpectrumLayerEditor
        attachedToLogo={Boolean(templateDraft?.spectrumAttachToLogo && templateDraft.logoEnabled)}
        inspectorState={selectedLayerInspectorState}
        layerCount={editableSpectrumLayers.length}
        layerOptions={layerOptions}
        spectrumDraft={draftSlices!.spectrum}
        selectedLayerIndexValue={selectedLayerKey}
        selectedLayerRecord={selectedLayerRecord}
        onAddLayer={onAddLayer}
        onDeleteLayer={onDeleteLayer}
        onDuplicateLayer={onDuplicateLayer}
        onFlushLayerCommit={onFlushSpectrumLayerCommit}
        onPatchLayer={onPatchLayer}
        onPatchLayerColor={onPatchLayerColor}
        onPatchSpectrumDraft={onPatchSpectrumDraft}
        onSelectLayer={onSelectLayer}
      />
    )
  }

  const activeTabPanel = (() => {
    if (!draftSlices) {
      return null
    }
    switch (activeTab) {
      case 'background':
        return (
          <BackgroundInspector
            draft={draftSlices.background}
            onPatchDraft={onPatchBackgroundDraft}
            onResetTransform={onResetBackgroundTransform}
          />
        )
      case 'logo':
        return (
          <LogoInspector
            draft={draftSlices.logo}
            onApplyLogoShape={onApplyLogoShape}
            onApplyLogoSize={onApplyLogoSize}
            onPatchDraft={onPatchLogoDraft}
            onSelectLogo={onSelectLogo}
            onSetSpectrumLogoGap={onSetSpectrumLogoGap}
            onToggleSpectrumAttachment={onToggleSpectrumAttachment}
          />
        )
      case 'particles':
        return (
          <ParticlesInspector
            draft={draftSlices.particles}
            onPatchDraft={onPatchParticlesDraft}
          />
        )
      case 'spectrum':
      default:
        return (
          <SpectrumInspector
            draft={draftSlices.spectrum}
            renderLayersCard={renderSpectrumLayersCard}
            onApplyPreset={onApplySpectrumPreset}
            onPatchDraft={onPatchSpectrumDraft}
          />
        )
    }
  })()

  const renderTextTab = () => (
    <TextLayerListPanel
      selectedTextOverlay={selectedTextOverlay}
      selectedTextOverlayIndex={selectedTextOverlayIndex}
      setSelectedTextOverlayKey={onSetSelectedTextOverlayKey}
      setSidePanelTab={onSetSidePanelTab}
      setTextPresetId={onSetTextPresetId}
      textOverlays={textOverlays}
      textPresetId={textPresetId}
      onAddTextOverlay={onAddTextOverlay}
      onApplyTextPreset={onApplyTextPreset}
      onDeleteTextOverlay={onDeleteTextOverlay}
      onDuplicateTextOverlay={onDuplicateTextOverlay}
      onMoveTextOverlay={onMoveTextOverlay}
    />
  )

  const selectedRunLabel = selectedPipelineRow
    ? `${selectedPipelineRow.channel} - ${selectedPipelineRow.run_date} - ${String(selectedPipelineRow.meta.role).toUpperCase()}`
    : 'No pipeline run selected'
  const branchLabel = selectedPipelineBranch === 'long' ? 'Long 16:9' : 'Reel 9:16'
  const exportReadyTone = workspace?.export.running ? 'running' : resolvedPipelineInputs.ready ? 'ready' : pipelineRows.length ? 'warning' : 'neutral'
  const exportReadyLabel = workspace?.export.running
    ? 'Export Running'
    : resolvedPipelineInputs.ready
      ? 'Export Ready'
      : pipelineRows.length
        ? 'Missing Assets'
        : 'No Run'
  const previewTitle = workspace?.ui.previewTitle || `Preview: ${templateNameDraft || 'Untitled'}`
  const currentBackgroundPath = backgroundPathDraft || workspace?.backgroundPath || resolvedPipelineInputs.backgroundPath || ''
  const currentBackgroundSourceLabel =
    backgroundPathDraft || workspace?.backgroundPath
      ? 'Manual preview background'
      : resolvedPipelineInputs.backgroundPath
        ? 'Selected pipeline branch background'
        : 'No background attached'
  const currentLogoPath = templateDraft?.logoPath || workspace?.logoPath || ''
  const currentTrackLabel = getFileName(previewTrackPath)
  const previewDurationLabel = `${formatSeconds(previewPlayback.currentTimeSec)} / ${formatSeconds(previewPlayback.durationSec)}`
  const activeTabDirty = activeTab === 'spectrum' ? draftDirtyState.spectrum : draftDirtyState[activeTab]
  const rightPanelSubtitle =
    sidePanelTab === 'export'
      ? 'Export controls and run selection.'
      : selectedTextOverlay
        ? `Editing ${selectedTextOverlay.text.trim().split('\n')[0]?.trim() || `Text ${selectedTextOverlayIndex + 1}`}`
        : 'Select a text layer to edit it.'

  const exportPanel = (
    <ExportQueuePanel
      buildVideoPipelineRunKey={buildVideoPipelineRunKey}
      exportState={workspace?.export ?? {}}
      formatPath={formatPath}
      isProgressLoading={progressIsLoading}
      mp3List={workspace?.mp3List ?? []}
      onApplyPreviewMp3Selection={onApplyPreviewMp3Selection}
      onHandleSelectPreviewMp3={onHandleSelectPreviewMp3}
      onOpenExportOutputFile={onOpenExportOutputFile}
      onOpenExportOutputFolder={onOpenExportOutputFolder}
      onSelectAndPlayPreviewMp3={onSelectAndPlayPreviewMp3}
      onStartExport={onStartPipelineExport}
      onStopExport={onStopPipelineExport}
      pipelineRows={pipelineRows}
      resolvedPipelineInputs={resolvedPipelineInputs}
      selectedMp3Path={workspace?.selectedMp3Path ?? ''}
      selectedPipelineBranch={selectedPipelineBranch}
      selectedPipelineRow={selectedPipelineRow}
      selectedPipelineRunKey={selectedPipelineRow ? buildVideoPipelineRunKey(selectedPipelineRow) : ''}
      setSelectedPipelineBranch={(value) => onSetSelectedPipelineBranch((value || 'long') as VideoPipelineBranch)}
      setSelectedPipelineRunKey={onSetSelectedPipelineRunKey}
      startManualExportPending={startManualExportPending}
      startPipelineExportPending={startPipelineExportPending}
      onStartManualExport={onStartManualExport}
      stopPipelineExportPending={stopPipelineExportPending}
    />
  )

  const diagnosticsPanel = (
    <VideoWorkspaceDiagnosticsPanel
      backgroundLabel={diagnosticsState.backgroundLabel}
      branchLabel={diagnosticsState.branchLabel}
      canResetLocalDraft={diagnosticsState.canResetLocalDraft}
      dirtyDomains={diagnosticsState.dirtyDomains}
      exportStatusLabel={diagnosticsState.exportStatusLabel}
      exportStatusTone={diagnosticsState.exportStatusTone}
      pipelineStatusLabel={diagnosticsState.pipelineStatusLabel}
      pipelineStatusTone={diagnosticsState.pipelineStatusTone}
      previewGuidanceDetail={diagnosticsState.previewGuidanceDetail}
      previewGuidanceItems={diagnosticsState.previewGuidanceItems}
      previewGuidanceTitle={diagnosticsState.previewGuidanceTitle}
      previewGuidanceTone={diagnosticsState.previewGuidanceTone}
      previewNeedsAttention={diagnosticsState.previewNeedsAttention}
      previewStatusLabel={diagnosticsState.previewStatusLabel}
      previewStatusMessage={diagnosticsState.previewStatusMessage}
      previewStatusTone={diagnosticsState.previewStatusTone}
      saveStatusLabel={diagnosticsState.saveStatusLabel}
      saveStatusTone={diagnosticsState.saveStatusTone}
      templateId={diagnosticsState.templateId}
      trackLabel={diagnosticsState.trackLabel}
      onCopyDiagnostics={diagnosticsState.onCopyDiagnostics}
      onRefreshWorkspace={diagnosticsState.onRefreshWorkspace}
      onRemountPreview={diagnosticsState.onRemountPreview}
      onResetLocalDraft={diagnosticsState.onResetLocalDraft}
    />
  )

  return (
    <div className="grid h-full min-h-0 gap-4 overflow-hidden xl:grid-cols-[320px_minmax(0,1fr)_320px] 2xl:grid-cols-[336px_minmax(0,1fr)_336px]">
      <VideoWorkspaceLeftRail
        activeTab={activeTab}
        activeTabDirty={activeTabDirty}
        activeTabPanel={activeTabPanel}
        diagnosticsPanel={diagnosticsPanel}
        deleteTemplatePending={deleteTemplatePending}
        isLoading={isLoading}
        patchTemplatePending={patchTemplatePending}
        saveTemplatePending={saveTemplatePending}
        selectedTemplateId={selectedTemplateId}
        settingsTabs={settingsTabs}
        templateNameDraft={templateNameDraft}
        templates={templates}
        workspaceDirty={workspaceDirty}
        onActiveTabChange={onActiveTabChange}
        onDelete={() => void onDeleteTemplate()}
        onSave={() => void onSaveTemplate()}
        onTemplateNameChange={onSetTemplateNameDraft}
        onTemplateSelectionChange={onHandleTemplateSelectionChange}
      />

      <VideoWorkspaceStage
        branchLabel={branchLabel}
        currentBackgroundFileName={getFileName(currentBackgroundPath)}
        currentBackgroundPath={currentBackgroundPath}
        currentBackgroundSourceLabel={currentBackgroundSourceLabel}
        currentLogoFileName={getFileName(currentLogoPath)}
        currentLogoPath={currentLogoPath}
        currentRunDirectory={resolvedPipelineInputs.runDir || ''}
        currentRunDirectoryFileName={getFileName(resolvedPipelineInputs.runDir || '')}
        currentTrackDetail={previewTrackPath || 'No preview MP3 attached'}
        currentTrackLabel={currentTrackLabel}
        durationLabel={previewDurationLabel}
        exportReadyLabel={exportReadyLabel}
        exportReadyTone={exportReadyTone}
        issuePreviewPlaybackCommand={onIssuePreviewPlaybackCommand}
        onEditLayers={() => onActiveTabChange('spectrum')}
        onEditLogo={() => onActiveTabChange('logo')}
        onOpenExport={() => onSetSidePanelTab('export')}
        onOutputResolutionChange={(value) => {
          const next = String(value || '').trim()
          if (!next || next === (workspace?.outputResolution ?? '')) {
            return
          }
          onSaveOutputResolution(next)
        }}
        onPreviewLifecycleStateChange={onHandlePreviewLifecycleStateChange}
        enableSpectrumPositionEditing={activeTab === 'spectrum'}
        onSpectrumPositionChange={onPatchSpectrumDraft}
        onPlaybackStateChange={onSetPreviewPlayback}
        onSelectBackground={() => {
          void onHandleSelectBackground()
        }}
        onSelectPreviewMp3={() => {
          void onHandleSelectPreviewMp3()
        }}
        outputResolution={workspace?.outputResolution ?? ''}
        previewGuidanceDetail={diagnosticsState.previewGuidanceDetail}
        previewGuidanceItems={diagnosticsState.previewGuidanceItems}
        previewGuidanceTitle={diagnosticsState.previewGuidanceTitle}
        previewGuidanceTone={diagnosticsState.previewGuidanceTone}
        previewNeedsAttention={diagnosticsState.previewNeedsAttention}
        previewStatusLabel={diagnosticsState.previewStatusLabel}
        previewStatusTone={diagnosticsState.previewStatusTone}
        previewAspectStyle={previewAspectStyle}
        previewRuntimeNonce={diagnosticsState.previewRuntimeNonce}
        previewPlayback={previewPlayback}
        previewPlaybackCommand={previewPlaybackCommand}
        previewTemplate={previewTemplate}
        previewTitle={previewTitle}
        previewTrackPath={previewTrackPath}
        renderTextTab={renderTextTab}
        saveOutputResolutionPending={saveOutputResolutionPending}
        selectedRunLabel={selectedRunLabel}
        selectedTextOverlayIndex={selectedTextOverlayIndex}
        templateDraft={templateDraft}
        textSelectionLabel={selectedTextOverlay ? `Selected ${selectedTextOverlayIndex + 1}/${textOverlays.length}` : 'No selection'}
        textSelectionTone={selectedTextOverlay ? 'ready' : 'neutral'}
        workspace={{
          previewAspectRatio: workspace?.previewAspectRatio ?? {
            width: 16,
            height: 9,
          },
        }}
      />

      <VideoWorkspaceRightRail
        applyTextAnchorAlignment={onApplyTextAnchorAlignment}
        applyTextCase={onApplyTextCase}
        applyTextPreset={onApplyTextPreset}
        backgroundPath={currentBackgroundPath}
        exportPanel={exportPanel}
        getTextAnchorAlignment={getTextAnchorAlignment}
        logoPath={currentLogoPath}
        playbackCommand={previewPlaybackCommand}
        previewTemplate={previewTemplate}
        rightPanelSubtitle={rightPanelSubtitle}
        selectedLayerLabel={selectedLayerInspectorState.layerName}
        selectedMp3Path={previewTrackPath}
        selectedTextOverlay={selectedTextOverlay}
        selectedTextOverlayIndex={selectedTextOverlayIndex}
        sidePanelTab={sidePanelTab}
        templateDraft={templateDraft}
        textPanelMode={textPanelMode}
        updateTextOverlay={onUpdateTextOverlay}
        onSetSidePanelTab={onSetSidePanelTab}
        onSetTextPanelMode={onSetTextPanelMode}
        workspace={{
          playback: previewPlayback,
          previewAspectRatio: workspace?.previewAspectRatio ?? {
            width: 16,
            height: 9,
          },
        }}
      />
    </div>
  )
}
