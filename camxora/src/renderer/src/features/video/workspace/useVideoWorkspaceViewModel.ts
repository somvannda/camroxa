import { useMemo } from 'react'

import type { CompactTabOption } from '@/shared/ui/compact-tabs'
import type { VideoWorkspaceState } from '@/shared/types/desktop'
import type { ResolvedVideoPipelineInputs } from '@/shared/lib/videoPipelineInputs'
import type { ProgressRowResponse } from '@/shared/api/platformEndpoints'
import { type VideoWorkspaceShellProps } from '@/features/video/workspace/VideoWorkspaceShell'
import { type VideoWorkspaceDraftDirtyState, type VideoWorkspaceDraftSlices } from '@/features/video/workspace/templateDraftDomains'
import type { PreviewLifecycleState } from '@/features/video/preview/previewLifecycleState'
import type { PreviewPlaybackCommand } from '@/features/video/preview/transportClock'
import type { TemplateSettingsDraft, TemplateTextOverlayDraft } from '@/features/settings/settingsTemplateDraft'
import type { PreviewPlaybackState, VideoTabId } from '@/features/video/workspace/useVideoWorkspaceShell'
import type { VideoWorkspaceDiagnosticsState } from '@/features/video/workspace/useVideoWorkspaceDiagnostics'

type UseVideoWorkspaceViewModelOptions = {
  workspace: VideoWorkspaceState | undefined
  isLoading: boolean
  progressIsLoading: boolean
  settingsTabs: ReadonlyArray<CompactTabOption>
  draftState: {
    currentTemplate: Record<string, unknown>
    diagnosticsState: VideoWorkspaceDiagnosticsState
    draftDirtyState: VideoWorkspaceDraftDirtyState
    draftSlices: VideoWorkspaceDraftSlices | null
    editableSpectrumLayers: Record<string, unknown>[]
    templateDraft: TemplateSettingsDraft | null
    templateNameDraft: string
    setTemplateNameDraft: VideoWorkspaceShellProps['onSetTemplateNameDraft']
    workspaceDirty: boolean
  }
  effectPackState: {
    backgroundEffectPackOptions: VideoWorkspaceShellProps['backgroundEffectPackOptions']
    backgroundEffectPackSelectionValue: string
    backgroundEffectPackStatus: VideoWorkspaceShellProps['backgroundEffectPackStatus']
    effectPackBusy: boolean
    logoEffectPackOptions: VideoWorkspaceShellProps['logoEffectPackOptions']
    logoEffectPackSelectionValue: string
    logoEffectPackStatus: VideoWorkspaceShellProps['logoEffectPackStatus']
    particlesEffectPackOptions: VideoWorkspaceShellProps['particlesEffectPackOptions']
    particlesEffectPackSelectionValue: string
    particlesEffectPackStatus: VideoWorkspaceShellProps['particlesEffectPackStatus']
    spectrumEffectPackOptions: VideoWorkspaceShellProps['spectrumEffectPackOptions']
    spectrumEffectPackSelectionValue: string
    spectrumEffectPackStatus: VideoWorkspaceShellProps['spectrumEffectPackStatus']
  }
  shellState: {
    activeTab: VideoTabId
    backgroundPathDraft: string
    issuePreviewPlaybackCommand: VideoWorkspaceShellProps['onIssuePreviewPlaybackCommand']
    previewPlayback: PreviewPlaybackState
    previewPlaybackCommand: PreviewPlaybackCommand | null
    selectedLayerKey: string
    selectedPipelineBranch: VideoWorkspaceShellProps['selectedPipelineBranch']
    selectedTemplateId: string
    sidePanelTab: VideoWorkspaceShellProps['sidePanelTab']
    textPanelMode: VideoWorkspaceShellProps['textPanelMode']
    textPresetId: string
    setActiveTab: VideoWorkspaceShellProps['onActiveTabChange']
    setPreviewPlayback: VideoWorkspaceShellProps['onSetPreviewPlayback']
    setSelectedLayerKey: VideoWorkspaceShellProps['onSelectLayer']
    setSelectedPipelineBranch: VideoWorkspaceShellProps['onSetSelectedPipelineBranch']
    setSelectedPipelineRunKey: VideoWorkspaceShellProps['onSetSelectedPipelineRunKey']
    setSelectedTextOverlayKey: VideoWorkspaceShellProps['onSetSelectedTextOverlayKey']
    setSidePanelTab: VideoWorkspaceShellProps['onSetSidePanelTab']
    setTextPanelMode: VideoWorkspaceShellProps['onSetTextPanelMode']
    setTextPresetId: VideoWorkspaceShellProps['onSetTextPresetId']
  }
  selectionState: {
    layerOptions: Array<{ label: string; value: string }>
    pipelineRows: ProgressRowResponse[]
    previewAspectStyle: React.CSSProperties
    previewTemplate: Record<string, unknown>
    previewTrackPath: string
    resolvedPipelineInputs: ResolvedVideoPipelineInputs
    selectedLayerIndex: number | undefined
    selectedLayerRecord: Record<string, unknown> | null
    selectedPipelineRow: ProgressRowResponse | null
  }
  commandState: {
    applyPreviewMp3Selection: VideoWorkspaceShellProps['onApplyPreviewMp3Selection']
    deleteTemplatePending: boolean
    handleDeleteTemplate: VideoWorkspaceShellProps['onDeleteTemplate']
    handleSelectBackground: VideoWorkspaceShellProps['onHandleSelectBackground']
    openExportOutputFile: VideoWorkspaceShellProps['onOpenExportOutputFile']
    openExportOutputFolder: VideoWorkspaceShellProps['onOpenExportOutputFolder']
    handlePreviewLifecycleStateChange: (state: PreviewLifecycleState) => void
    handleSelectPreviewMp3: VideoWorkspaceShellProps['onHandleSelectPreviewMp3']
    handleTemplateSelectionChange: VideoWorkspaceShellProps['onHandleTemplateSelectionChange']
    patchTemplatePending: boolean
    saveOutputResolution: VideoWorkspaceShellProps['onSaveOutputResolution']
    saveOutputResolutionPending: boolean
    saveWorkspaceTemplate: VideoWorkspaceShellProps['onSaveTemplate']
    saveTemplatePending: boolean
    selectAndPlayPreviewMp3: VideoWorkspaceShellProps['onSelectAndPlayPreviewMp3']
    startManualExport: VideoWorkspaceShellProps['onStartManualExport']
    startManualExportPending: boolean
    startPipelineExport: VideoWorkspaceShellProps['onStartPipelineExport']
    startPipelineExportPending: boolean
    stopPipelineExport: VideoWorkspaceShellProps['onStopPipelineExport']
    stopPipelineExportPending: boolean
  }
  effectPackCommandState: {
    activateBackgroundEffectPackVersion: VideoWorkspaceShellProps['onActivateBackgroundEffectPackVersion']
    activateLogoEffectPackVersion: VideoWorkspaceShellProps['onActivateLogoEffectPackVersion']
    activateParticlesEffectPackVersion: VideoWorkspaceShellProps['onActivateParticlesEffectPackVersion']
    activateSpectrumEffectPackVersion: VideoWorkspaceShellProps['onActivateSpectrumEffectPackVersion']
    applyBackgroundEffectPack: VideoWorkspaceShellProps['onApplyBackgroundEffectPack']
    applyLogoEffectPack: VideoWorkspaceShellProps['onApplyLogoEffectPack']
    applyParticlesEffectPack: VideoWorkspaceShellProps['onApplyParticlesEffectPack']
    applySpectrumEffectPack: VideoWorkspaceShellProps['onApplySpectrumEffectPack']
    clearBackgroundEffectPack: VideoWorkspaceShellProps['onClearBackgroundEffectPack']
    clearLogoEffectPack: VideoWorkspaceShellProps['onClearLogoEffectPack']
    clearParticlesEffectPack: VideoWorkspaceShellProps['onClearParticlesEffectPack']
    clearSpectrumEffectPack: VideoWorkspaceShellProps['onClearSpectrumEffectPack']
    installEffectPack: VideoWorkspaceShellProps['onInstallEffectPack']
    reloadEffectPacks: VideoWorkspaceShellProps['onReloadEffectPacks']
    removeBackgroundEffectPackVersion: VideoWorkspaceShellProps['onRemoveBackgroundEffectPackVersion']
    removeLogoEffectPackVersion: VideoWorkspaceShellProps['onRemoveLogoEffectPackVersion']
    removeParticlesEffectPackVersion: VideoWorkspaceShellProps['onRemoveParticlesEffectPackVersion']
    removeSpectrumEffectPackVersion: VideoWorkspaceShellProps['onRemoveSpectrumEffectPackVersion']
    toggleBackgroundEffectPackEnabled: VideoWorkspaceShellProps['onToggleBackgroundEffectPackEnabled']
    toggleLogoEffectPackEnabled: VideoWorkspaceShellProps['onToggleLogoEffectPackEnabled']
    toggleParticlesEffectPackEnabled: VideoWorkspaceShellProps['onToggleParticlesEffectPackEnabled']
    toggleSpectrumEffectPackEnabled: VideoWorkspaceShellProps['onToggleSpectrumEffectPackEnabled']
  }
  spectrumState: {
    applySpectrumPreset: VideoWorkspaceShellProps['onApplySpectrumPreset']
    flushSpectrumLayerCommit: VideoWorkspaceShellProps['onFlushSpectrumLayerCommit']
    handleAddLayer: VideoWorkspaceShellProps['onAddLayer']
    handleDeleteLayer: VideoWorkspaceShellProps['onDeleteLayer']
    handleDuplicateLayer: VideoWorkspaceShellProps['onDuplicateLayer']
    patchSelectedLayer: VideoWorkspaceShellProps['onPatchLayer']
    patchSelectedLayerColor: VideoWorkspaceShellProps['onPatchLayerColor']
    patchSpectrumDraft: VideoWorkspaceShellProps['onPatchSpectrumDraft']
  }
  backgroundState: {
    patchBackgroundDraft: VideoWorkspaceShellProps['onPatchBackgroundDraft']
    resetBackgroundTransform: VideoWorkspaceShellProps['onResetBackgroundTransform']
  }
  logoState: {
    applyLogoShape: VideoWorkspaceShellProps['onApplyLogoShape']
    applyLogoSize: VideoWorkspaceShellProps['onApplyLogoSize']
    patchLogoDraft: VideoWorkspaceShellProps['onPatchLogoDraft']
    selectLogo: VideoWorkspaceShellProps['onSelectLogo']
    setSpectrumLogoGap: VideoWorkspaceShellProps['onSetSpectrumLogoGap']
    toggleSpectrumAttachment: VideoWorkspaceShellProps['onToggleSpectrumAttachment']
  }
  particlesState: {
    patchParticlesDraft: VideoWorkspaceShellProps['onPatchParticlesDraft']
  }
  textState: {
    addTextOverlay: VideoWorkspaceShellProps['onAddTextOverlay']
    applyTextAnchorAlignment: VideoWorkspaceShellProps['onApplyTextAnchorAlignment']
    applyTextCase: VideoWorkspaceShellProps['onApplyTextCase']
    applyTextPreset: VideoWorkspaceShellProps['onApplyTextPreset']
    deleteTextOverlay: VideoWorkspaceShellProps['onDeleteTextOverlay']
    duplicateTextOverlay: VideoWorkspaceShellProps['onDuplicateTextOverlay']
    moveTextOverlay: VideoWorkspaceShellProps['onMoveTextOverlay']
    selectedTextOverlay: TemplateTextOverlayDraft | null
    selectedTextOverlayIndex: number
    textOverlays: TemplateTextOverlayDraft[]
    updateTextOverlay: VideoWorkspaceShellProps['onUpdateTextOverlay']
  }
  getTextAnchorAlignment: VideoWorkspaceShellProps['getTextAnchorAlignment']
}

export function useVideoWorkspaceViewModel({
  workspace,
  isLoading,
  progressIsLoading,
  settingsTabs,
  draftState,
  shellState,
  selectionState,
  commandState,
  effectPackState,
  effectPackCommandState,
  spectrumState,
  backgroundState,
  logoState,
  particlesState,
  textState,
  getTextAnchorAlignment,
}: UseVideoWorkspaceViewModelOptions): VideoWorkspaceShellProps {
  return useMemo(
    () => ({
      activeTab: shellState.activeTab,
      backgroundPathDraft: shellState.backgroundPathDraft,
      diagnosticsState: draftState.diagnosticsState,
      draftDirtyState: draftState.draftDirtyState,
      draftSlices: draftState.draftSlices,
      deleteTemplatePending: commandState.deleteTemplatePending,
      editableSpectrumLayers: draftState.editableSpectrumLayers,
      effectPackBusy: effectPackState.effectPackBusy,
      getTextAnchorAlignment,
      isLoading,
      layerOptions: selectionState.layerOptions,
      patchTemplatePending: commandState.patchTemplatePending,
      pipelineRows: selectionState.pipelineRows,
      previewAspectStyle: selectionState.previewAspectStyle,
      previewPlayback: shellState.previewPlayback,
      previewPlaybackCommand: shellState.previewPlaybackCommand,
      previewTemplate: selectionState.previewTemplate,
      previewTrackPath: selectionState.previewTrackPath,
      progressIsLoading,
      resolvedPipelineInputs: selectionState.resolvedPipelineInputs,
      saveOutputResolutionPending: commandState.saveOutputResolutionPending,
      saveTemplatePending: commandState.saveTemplatePending,
      selectedLayerIndex: selectionState.selectedLayerIndex,
      selectedLayerKey: shellState.selectedLayerKey,
      selectedLayerRecord: selectionState.selectedLayerRecord,
      selectedPipelineBranch: shellState.selectedPipelineBranch,
      selectedPipelineRow: selectionState.selectedPipelineRow,
      selectedTemplateId: shellState.selectedTemplateId,
      selectedTextOverlay: textState.selectedTextOverlay,
      selectedTextOverlayIndex: textState.selectedTextOverlayIndex,
      settingsTabs,
      sidePanelTab: shellState.sidePanelTab,
      spectrumEffectPackOptions: effectPackState.spectrumEffectPackOptions,
      spectrumEffectPackSelectionValue: effectPackState.spectrumEffectPackSelectionValue,
      spectrumEffectPackStatus: effectPackState.spectrumEffectPackStatus,
      backgroundEffectPackOptions: effectPackState.backgroundEffectPackOptions,
      backgroundEffectPackSelectionValue: effectPackState.backgroundEffectPackSelectionValue,
      backgroundEffectPackStatus: effectPackState.backgroundEffectPackStatus,
      logoEffectPackOptions: effectPackState.logoEffectPackOptions,
      logoEffectPackSelectionValue: effectPackState.logoEffectPackSelectionValue,
      logoEffectPackStatus: effectPackState.logoEffectPackStatus,
      particlesEffectPackOptions: effectPackState.particlesEffectPackOptions,
      particlesEffectPackSelectionValue: effectPackState.particlesEffectPackSelectionValue,
      particlesEffectPackStatus: effectPackState.particlesEffectPackStatus,
      startManualExportPending: commandState.startManualExportPending,
      startPipelineExportPending: commandState.startPipelineExportPending,
      stopPipelineExportPending: commandState.stopPipelineExportPending,
      templateDraft: draftState.templateDraft,
      templateNameDraft: draftState.templateNameDraft,
      templates: workspace?.templates ?? [],
      textOverlays: textState.textOverlays,
      textPanelMode: shellState.textPanelMode,
      textPresetId: shellState.textPresetId,
      workspaceDirty: draftState.workspaceDirty,
      workspace,
      onActiveTabChange: shellState.setActiveTab,
      onAddLayer: spectrumState.handleAddLayer,
      onAddTextOverlay: textState.addTextOverlay,
      onApplyLogoShape: logoState.applyLogoShape,
      onApplyLogoSize: logoState.applyLogoSize,
      onApplyBackgroundEffectPack: effectPackCommandState.applyBackgroundEffectPack,
      onApplyLogoEffectPack: effectPackCommandState.applyLogoEffectPack,
      onApplyParticlesEffectPack: effectPackCommandState.applyParticlesEffectPack,
      onApplyPreviewMp3Selection: commandState.applyPreviewMp3Selection,
      onApplySpectrumEffectPack: effectPackCommandState.applySpectrumEffectPack,
      onApplySpectrumPreset: spectrumState.applySpectrumPreset,
      onApplyTextAnchorAlignment: textState.applyTextAnchorAlignment,
      onApplyTextCase: textState.applyTextCase,
      onApplyTextPreset: textState.applyTextPreset,
      onDeleteLayer: spectrumState.handleDeleteLayer,
      onDeleteTemplate: commandState.handleDeleteTemplate,
      onDeleteTextOverlay: textState.deleteTextOverlay,
      onDuplicateLayer: spectrumState.handleDuplicateLayer,
      onDuplicateTextOverlay: textState.duplicateTextOverlay,
      onFlushSpectrumLayerCommit: spectrumState.flushSpectrumLayerCommit,
      onHandleSelectBackground: commandState.handleSelectBackground,
      onHandlePreviewLifecycleStateChange: commandState.handlePreviewLifecycleStateChange,
      onHandleSelectPreviewMp3: commandState.handleSelectPreviewMp3,
      onOpenExportOutputFile: commandState.openExportOutputFile,
      onOpenExportOutputFolder: commandState.openExportOutputFolder,
      onHandleTemplateSelectionChange: commandState.handleTemplateSelectionChange,
      onInstallEffectPack: effectPackCommandState.installEffectPack,
      onIssuePreviewPlaybackCommand: shellState.issuePreviewPlaybackCommand,
      onMoveTextOverlay: textState.moveTextOverlay,
      onPatchBackgroundDraft: backgroundState.patchBackgroundDraft,
      onPatchLayer: spectrumState.patchSelectedLayer,
      onPatchLayerColor: spectrumState.patchSelectedLayerColor,
      onPatchLogoDraft: logoState.patchLogoDraft,
      onPatchParticlesDraft: particlesState.patchParticlesDraft,
      onPatchSpectrumDraft: spectrumState.patchSpectrumDraft,
      onResetBackgroundTransform: backgroundState.resetBackgroundTransform,
      onReloadEffectPacks: effectPackCommandState.reloadEffectPacks,
      onSaveOutputResolution: commandState.saveOutputResolution,
      onSaveTemplate: commandState.saveWorkspaceTemplate,
      onSelectAndPlayPreviewMp3: commandState.selectAndPlayPreviewMp3,
      onSelectLayer: shellState.setSelectedLayerKey,
      onSelectLogo: logoState.selectLogo,
      onSetPreviewPlayback: shellState.setPreviewPlayback,
      onSetSelectedPipelineBranch: shellState.setSelectedPipelineBranch,
      onSetSelectedPipelineRunKey: shellState.setSelectedPipelineRunKey,
      onSetSelectedTextOverlayKey: shellState.setSelectedTextOverlayKey,
      onSetSidePanelTab: shellState.setSidePanelTab,
      onSetSpectrumLogoGap: logoState.setSpectrumLogoGap,
      onSetTemplateNameDraft: draftState.setTemplateNameDraft,
      onSetTextPanelMode: shellState.setTextPanelMode,
      onSetTextPresetId: shellState.setTextPresetId,
      onStartManualExport: commandState.startManualExport,
      onStartPipelineExport: commandState.startPipelineExport,
      onStopPipelineExport: commandState.stopPipelineExport,
      onToggleBackgroundEffectPackEnabled: effectPackCommandState.toggleBackgroundEffectPackEnabled,
      onToggleLogoEffectPackEnabled: effectPackCommandState.toggleLogoEffectPackEnabled,
      onToggleParticlesEffectPackEnabled: effectPackCommandState.toggleParticlesEffectPackEnabled,
      onToggleSpectrumEffectPackEnabled: effectPackCommandState.toggleSpectrumEffectPackEnabled,
      onToggleSpectrumAttachment: logoState.toggleSpectrumAttachment,
      onUpdateTextOverlay: textState.updateTextOverlay,
      onActivateBackgroundEffectPackVersion: effectPackCommandState.activateBackgroundEffectPackVersion,
      onActivateLogoEffectPackVersion: effectPackCommandState.activateLogoEffectPackVersion,
      onActivateParticlesEffectPackVersion: effectPackCommandState.activateParticlesEffectPackVersion,
      onActivateSpectrumEffectPackVersion: effectPackCommandState.activateSpectrumEffectPackVersion,
      onClearBackgroundEffectPack: effectPackCommandState.clearBackgroundEffectPack,
      onClearLogoEffectPack: effectPackCommandState.clearLogoEffectPack,
      onClearParticlesEffectPack: effectPackCommandState.clearParticlesEffectPack,
      onClearSpectrumEffectPack: effectPackCommandState.clearSpectrumEffectPack,
      onRemoveBackgroundEffectPackVersion: effectPackCommandState.removeBackgroundEffectPackVersion,
      onRemoveLogoEffectPackVersion: effectPackCommandState.removeLogoEffectPackVersion,
      onRemoveParticlesEffectPackVersion: effectPackCommandState.removeParticlesEffectPackVersion,
      onRemoveSpectrumEffectPackVersion: effectPackCommandState.removeSpectrumEffectPackVersion,
    }),
    [
      effectPackCommandState.activateBackgroundEffectPackVersion,
      effectPackCommandState.activateLogoEffectPackVersion,
      effectPackCommandState.activateParticlesEffectPackVersion,
      effectPackCommandState.activateSpectrumEffectPackVersion,
      effectPackCommandState.applyBackgroundEffectPack,
      effectPackCommandState.applyLogoEffectPack,
      effectPackCommandState.applyParticlesEffectPack,
      effectPackCommandState.applySpectrumEffectPack,
      effectPackCommandState.clearBackgroundEffectPack,
      effectPackCommandState.clearLogoEffectPack,
      effectPackCommandState.clearParticlesEffectPack,
      effectPackCommandState.clearSpectrumEffectPack,
      effectPackCommandState.installEffectPack,
      effectPackCommandState.reloadEffectPacks,
      effectPackCommandState.removeBackgroundEffectPackVersion,
      effectPackCommandState.removeLogoEffectPackVersion,
      effectPackCommandState.removeParticlesEffectPackVersion,
      effectPackCommandState.removeSpectrumEffectPackVersion,
      effectPackCommandState.toggleBackgroundEffectPackEnabled,
      effectPackCommandState.toggleLogoEffectPackEnabled,
      effectPackCommandState.toggleParticlesEffectPackEnabled,
      effectPackCommandState.toggleSpectrumEffectPackEnabled,
      effectPackState.backgroundEffectPackOptions,
      effectPackState.backgroundEffectPackSelectionValue,
      effectPackState.backgroundEffectPackStatus,
      effectPackState.effectPackBusy,
      effectPackState.logoEffectPackOptions,
      effectPackState.logoEffectPackSelectionValue,
      effectPackState.logoEffectPackStatus,
      effectPackState.particlesEffectPackOptions,
      effectPackState.particlesEffectPackSelectionValue,
      effectPackState.particlesEffectPackStatus,
      effectPackState.spectrumEffectPackOptions,
      effectPackState.spectrumEffectPackSelectionValue,
      effectPackState.spectrumEffectPackStatus,
      backgroundState.patchBackgroundDraft,
      backgroundState.resetBackgroundTransform,
      commandState.applyPreviewMp3Selection,
      commandState.deleteTemplatePending,
      commandState.handleDeleteTemplate,
      commandState.handleSelectBackground,
      commandState.handlePreviewLifecycleStateChange,
      commandState.handleSelectPreviewMp3,
      commandState.handleTemplateSelectionChange,
      commandState.patchTemplatePending,
      commandState.saveOutputResolution,
      commandState.saveOutputResolutionPending,
      commandState.saveWorkspaceTemplate,
      commandState.saveTemplatePending,
      commandState.selectAndPlayPreviewMp3,
      commandState.startManualExport,
      commandState.startManualExportPending,
      commandState.startPipelineExport,
      commandState.startPipelineExportPending,
      commandState.stopPipelineExport,
      commandState.stopPipelineExportPending,
      draftState.currentTemplate,
      draftState.diagnosticsState,
      draftState.draftDirtyState,
      draftState.draftSlices,
      draftState.editableSpectrumLayers,
      draftState.templateDraft,
      draftState.templateNameDraft,
      draftState.setTemplateNameDraft,
      draftState.workspaceDirty,
      getTextAnchorAlignment,
      isLoading,
      logoState.applyLogoShape,
      logoState.applyLogoSize,
      logoState.patchLogoDraft,
      logoState.selectLogo,
      logoState.setSpectrumLogoGap,
      logoState.toggleSpectrumAttachment,
      particlesState.patchParticlesDraft,
      progressIsLoading,
      selectionState.layerOptions,
      selectionState.pipelineRows,
      selectionState.previewAspectStyle,
      selectionState.previewTemplate,
      selectionState.previewTrackPath,
      selectionState.resolvedPipelineInputs,
      selectionState.selectedLayerIndex,
      selectionState.selectedLayerRecord,
      selectionState.selectedPipelineRow,
      settingsTabs,
      shellState.activeTab,
      shellState.backgroundPathDraft,
      shellState.issuePreviewPlaybackCommand,
      shellState.previewPlayback,
      shellState.previewPlaybackCommand,
      shellState.selectedLayerKey,
      shellState.selectedPipelineBranch,
      shellState.selectedTemplateId,
      shellState.setActiveTab,
      shellState.setPreviewPlayback,
      shellState.setSelectedLayerKey,
      shellState.setSelectedPipelineBranch,
      shellState.setSelectedPipelineRunKey,
      shellState.setSelectedTextOverlayKey,
      shellState.setSidePanelTab,
      shellState.setTextPanelMode,
      shellState.setTextPresetId,
      shellState.sidePanelTab,
      shellState.textPanelMode,
      shellState.textPresetId,
      spectrumState.applySpectrumPreset,
      spectrumState.flushSpectrumLayerCommit,
      spectrumState.handleAddLayer,
      spectrumState.handleDeleteLayer,
      spectrumState.handleDuplicateLayer,
      spectrumState.patchSelectedLayer,
      spectrumState.patchSelectedLayerColor,
      spectrumState.patchSpectrumDraft,
      textState.addTextOverlay,
      textState.applyTextAnchorAlignment,
      textState.applyTextCase,
      textState.applyTextPreset,
      textState.deleteTextOverlay,
      textState.duplicateTextOverlay,
      textState.moveTextOverlay,
      textState.selectedTextOverlay,
      textState.selectedTextOverlayIndex,
      textState.textOverlays,
      textState.updateTextOverlay,
      workspace,
    ],
  )
}
