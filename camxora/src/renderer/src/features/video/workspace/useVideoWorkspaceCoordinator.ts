import { useCallback, useMemo, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import type { PreviewLifecycleState } from '@/features/video/preview/previewLifecycleState'
import { useProgressRowsQuery } from '@/features/shell/useProgressRowsQuery'
import { useSharedProfilesQuery } from '@/features/shell/useSharedProfilesQuery'
import { useVideoWorkspaceQuery } from '@/features/video/useVideoWorkspaceQuery'
import { createVideoDebugSender } from '@/features/video/videoDiagnostics'
import { useBackgroundEditor } from '@/features/video/workspace/useBackgroundEditor'
import { useLogoEditor } from '@/features/video/workspace/useLogoEditor'
import { useLogoSpectrumBindings } from '@/features/video/workspace/useLogoSpectrumBindings'
import { useParticlesEditor } from '@/features/video/workspace/useParticlesEditor'
import { useSpectrumEditor } from '@/features/video/workspace/useSpectrumEditor'
import { getTextAnchorAlignment, useTextEditor } from '@/features/video/workspace/useTextEditor'
import { useVideoWorkspaceCommands } from '@/features/video/workspace/useVideoWorkspaceCommands'
import { useVideoWorkspaceDraft } from '@/features/video/workspace/useVideoWorkspaceDraft'
import { useVideoWorkspaceShell } from '@/features/video/workspace/useVideoWorkspaceShell'
import { useVideoWorkspaceViewModel } from '@/features/video/workspace/useVideoWorkspaceViewModel'
import { useEffectPackManager } from '@/features/video/workspace/useEffectPackManager'
import { useVideoWorkspaceDiagnostics } from '@/features/video/workspace/useVideoWorkspaceDiagnostics'
import { useVideoWorkspaceTemplatePersistence } from '@/features/video/workspace/useVideoWorkspaceTemplatePersistence'
import type { VideoWorkspaceShellProps } from '@/features/video/workspace/VideoWorkspaceShell'
import { getDesktopApi } from '@/shared/api/desktop'
import { useAuthStore } from '@/shared/auth/sessionStore'
import { scopedStorageKey } from '@/shared/lib/localUserScope'
import { buildVideoPipelineRunKey, resolveVideoPipelineInputs } from '@/shared/lib/videoPipelineInputs'
import { emitShellStatus } from '@/shared/lib/shellStatus'
import { type CompactTabOption } from '@/shared/ui/compact-tabs'

const VIDEO_WORKSPACE_DRAFT_STORAGE_PREFIX = 'camxora.video.workspace-draft'

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function getTodayInputValue(): string {
  const today = new Date()
  const year = today.getFullYear()
  const month = String(today.getMonth() + 1).padStart(2, '0')
  const day = String(today.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function getDateOffsetInputValue(offsetDays: number): string {
  const date = new Date()
  date.setDate(date.getDate() + offsetDays)
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

export function useVideoWorkspaceCoordinator(): {
  isError: boolean
  workspaceViewModel: VideoWorkspaceShellProps
} {
  const desktopApi = getDesktopApi()
  const queryClient = useQueryClient()
  const activeUserId = useAuthStore((state) => state.activeUserId)
  const draftStoragePrefix = useMemo(
    () => scopedStorageKey(VIDEO_WORKSPACE_DRAFT_STORAGE_PREFIX, activeUserId),
    [activeUserId],
  )

  const debugSend = createVideoDebugSender({
    sessionId: 'spectrum-preset-reset',
    runId: 'pre-fix',
  })
  const [previewLifecycleState, setPreviewLifecycleState] = useState<PreviewLifecycleState | null>(null)

  const { data, isLoading, isError } = useVideoWorkspaceQuery()
  const settingsTabs: ReadonlyArray<CompactTabOption> = useMemo(
    () => [
      { value: 'spectrum', label: 'Spectrum' },
      { value: 'background', label: 'Background' },
      { value: 'logo', label: 'Logo' },
      { value: 'particles', label: 'Particles' },
    ],
    [],
  )
  const progressFilters = useMemo(
    () => ({
      limit: 80,
      activeOnly: false,
      fromDate: getDateOffsetInputValue(-30),
      toDate: getTodayInputValue(),
    }),
    [],
  )
  const progressQuery = useProgressRowsQuery(progressFilters, { refetchInterval: false })
  const profilesQuery = useSharedProfilesQuery()

  const {
    currentTemplate,
    draftDirtyState,
    draftSlices,
    editableSpectrumLayers,
    resetLocalDraft,
    setSpectrumLayersLive,
    setTemplateDraft,
    setTemplateNameDraft,
    templateDraft,
    templateNameDirty,
    templateNameDraft,
  } = useVideoWorkspaceDraft({
    workspace: data,
    storagePrefix: draftStoragePrefix,
    debugSend,
    onHydrated: () => setTextPresetId(''),
  })

  const previewTemplate = useMemo(
    () => ({
      ...currentTemplate,
      style: templateDraft?.style ?? String(currentTemplate.style ?? 'straight-bars'),
      templateName: templateNameDraft.trim() || String(currentTemplate.templateName ?? ''),
      layers: editableSpectrumLayers,
    }),
    [currentTemplate, editableSpectrumLayers, templateDraft?.style, templateNameDraft],
  )
  const previewTrackPath = useMemo(
    () => String(data?.selectedMp3Path || data?.mp3List[0]?.path || '').trim(),
    [data?.mp3List, data?.selectedMp3Path],
  )
  const layerItems = useMemo(
    () => editableSpectrumLayers.map((layer, index) => ({ index, layer })),
    [editableSpectrumLayers],
  )
  const layerOptions = useMemo(
    () =>
      layerItems.map(({ index, layer }) => {
        const record = isRecord(layer) ? layer : null
        return {
          label: String(record?.name ?? record?.label ?? record?.id ?? '').trim() || `Layer ${index + 1}`,
          value: String(index),
        }
      }),
    [layerItems],
  )
  const previewAspectStyle = useMemo(
    () => ({
      aspectRatio: `${data?.previewAspectRatio.width ?? 16} / ${data?.previewAspectRatio.height ?? 9}`,
    }),
    [data?.previewAspectRatio.height, data?.previewAspectRatio.width],
  )
  const pipelineRows = useMemo(
    () =>
      (progressQuery.data?.rows ?? []).filter(
        (row) =>
          Boolean(row.meta.run_dir) &&
          (Boolean(row.meta.background_16x9_path) ||
            Boolean(row.meta.background_9x16_path) ||
            Boolean(row.meta.thumbnail_16x9_path) ||
            Boolean(row.meta.thumbnail_9x16_path)),
      ),
    [progressQuery.data?.rows],
  )
  const profileById = useMemo(
    () => new Map((profilesQuery.data ?? []).map((profile) => [profile.id, profile])),
    [profilesQuery.data],
  )

  const {
    activeTab,
    backgroundPathDraft,
    issuePreviewPlaybackCommand,
    previewPlayback,
    previewPlaybackCommand,
    queuePreviewAutoplay,
    selectedLayerKey,
    selectedPipelineBranch,
    selectedPipelineRunKey,
    selectedTemplateId,
    selectedTextOverlayKey,
    setActiveTab,
    setBackgroundPathDraft,
    setPreviewPlayback,
    setSelectedLayerKey,
    setSelectedPipelineBranch,
    setSelectedPipelineRunKey,
    setSelectedTemplateId,
    setSelectedTextOverlayKey,
    setSidePanelTab,
    setTextPanelMode,
    setTextPresetId,
    sidePanelTab,
    textPanelMode,
    textPresetId,
  } = useVideoWorkspaceShell({
    workspace: data,
    previewTrackPath,
    layerKeys: layerItems.map(({ index }) => String(index)),
    pipelineRunKeys: pipelineRows.map((row) => buildVideoPipelineRunKey(row)),
    textOverlayCount: templateDraft?.textOverlays.length ?? 0,
  })

  const selectedLayerItem = useMemo(
    () => layerItems.find(({ index }) => String(index) === selectedLayerKey) ?? layerItems[0] ?? null,
    [layerItems, selectedLayerKey],
  )
  const selectedLayerRecord = isRecord(selectedLayerItem?.layer) ? selectedLayerItem.layer : null
  const selectedPipelineRow = useMemo(
    () => pipelineRows.find((row) => buildVideoPipelineRunKey(row) === selectedPipelineRunKey) ?? pipelineRows[0] ?? null,
    [pipelineRows, selectedPipelineRunKey],
  )
  const selectedPipelineProfile = selectedPipelineRow ? (profileById.get(selectedPipelineRow.meta.profile_id) ?? null) : null
  const resolvedPipelineInputs = useMemo(
    () => resolveVideoPipelineInputs(selectedPipelineRow, selectedPipelineBranch, selectedPipelineProfile),
    [selectedPipelineBranch, selectedPipelineProfile, selectedPipelineRow],
  )

  const {
    applyPreviewMp3Selection,
    deleteTemplatePending,
    handleDeleteTemplate,
    handleSelectBackground,
    handleSelectPreviewMp3,
    handleTemplateSelectionChange,
    openExportOutputFile,
    openExportOutputFolder,
    patchTemplate,
    patchTemplatePending,
    saveOutputResolution,
    saveOutputResolutionPending,
    saveTemplatePending,
    selectAndPlayPreviewMp3,
    startManualExport,
    startManualExportPending,
    startPipelineExport,
    startPipelineExportPending,
    stopPipelineExport,
    stopPipelineExportPending,
  } = useVideoWorkspaceCommands({
    debugSend,
    desktopApi,
    issuePreviewPlaybackCommand,
    previewTemplate,
    previewPlayback,
    previewTrackPath,
    queryClient,
    queuePreviewAutoplay,
    resolvedPipelineInputs,
    selectedPipelineBranch,
    selectedPipelineRow,
    setBackgroundPathDraft,
    setSelectedTemplateId,
    templateDraft,
    templateDraftStyle: templateDraft?.style,
    workspace: data,
  })

  const {
    applySpectrumPreset,
    commitSpectrumSessionDraft,
    flushSpectrumLayerCommit,
    handleAddLayer,
    handleDeleteLayer,
    handleDuplicateLayer,
    patchSelectedLayer,
    patchSelectedLayerColor,
    patchSpectrumDraft,
  } = useSpectrumEditor({
    currentTemplate,
    debugSend,
    editableSpectrumLayers,
    emitStatus: (tone, message) => emitShellStatus({ tone, message }),
    selectedLayerIndex: selectedLayerItem?.index ?? 0,
    setSelectedLayerKey,
    setSpectrumLayersLive,
    setTemplateDraft,
    templateDraft,
  })

  const effectPackManager = useEffectPackManager({
    currentTemplate,
    desktopApi,
    queryClient,
    setTemplateDraft,
    commitSpectrumSessionDraft,
    templateDraft,
    workspace: data,
  })

  const { patchBackgroundDraft, resetBackgroundTransform } = useBackgroundEditor({ setTemplateDraft, templateDraft })

  const { commitLogoDraft, selectLogo } = useLogoEditor({
    desktopApi,
    emitStatus: (tone, message) => emitShellStatus({ tone, message }),
    setTemplateDraft,
    templateDraft,
  })
  const {
    applyLogoShape,
    applyLogoSize,
    patchLogoDraft,
    setSpectrumLogoGap,
    toggleSpectrumAttachment,
  } = useLogoSpectrumBindings({
    commitLogoDraft,
    commitSpectrumSessionDraft,
    templateDraft,
  })

  const { patchParticlesDraft } = useParticlesEditor({ setTemplateDraft, templateDraft })

  const {
    addTextOverlay,
    applyTextAnchorAlignment,
    applyTextCase,
    applyTextPreset,
    deleteTextOverlay,
    duplicateTextOverlay,
    moveTextOverlay,
    selectedTextOverlay,
    selectedTextOverlayIndex,
    textOverlays,
    updateTextOverlay,
  } = useTextEditor({
    selectedTextOverlayKey,
    setSelectedTextOverlayKey,
    setSidePanelTab,
    setTemplateDraft,
    templateDraft,
  })

  const { saveWorkspaceTemplate, workspaceDirty } = useVideoWorkspaceTemplatePersistence({
    currentTemplate,
    draftDirtyState,
    editableSpectrumLayers,
    patchTemplate,
    templateDraft,
    templateNameDirty,
    templateNameDraft,
  })

  const diagnosticsState = useVideoWorkspaceDiagnostics({
    activeTab,
    backgroundPathDraft,
    currentTemplate,
    draftDirtyState,
    patchTemplatePending,
    previewLifecycleState,
    previewPlayback,
    previewTrackPath,
    queryClient,
    resetLocalDraft,
    resolvedPipelineInputs,
    saveTemplatePending,
    selectedPipelineBranch,
    selectedPipelineRow,
    templateNameDraft,
    workspace: data,
    workspaceDirty,
  })
  const handlePreviewLifecycleStateChange = useCallback((state: PreviewLifecycleState) => {
    setPreviewLifecycleState(state)
  }, [])

  const workspaceViewModel = useVideoWorkspaceViewModel({
    workspace: data,
    isLoading,
    progressIsLoading: progressQuery.isLoading,
    settingsTabs,
    draftState: {
      currentTemplate,
      diagnosticsState,
      draftDirtyState,
      draftSlices,
      editableSpectrumLayers,
      setTemplateNameDraft,
      templateDraft,
      templateNameDraft,
      workspaceDirty,
    },
    shellState: {
      activeTab,
      backgroundPathDraft,
      issuePreviewPlaybackCommand,
      previewPlayback,
      previewPlaybackCommand,
      selectedLayerKey,
      selectedPipelineBranch,
      selectedTemplateId,
      sidePanelTab,
      textPanelMode,
      textPresetId,
      setActiveTab,
      setPreviewPlayback,
      setSelectedLayerKey,
      setSelectedPipelineBranch,
      setSelectedPipelineRunKey,
      setSelectedTextOverlayKey,
      setSidePanelTab,
      setTextPanelMode,
      setTextPresetId,
    },
    selectionState: {
      layerOptions,
      pipelineRows,
      previewAspectStyle,
      previewTemplate,
      previewTrackPath,
      resolvedPipelineInputs,
      selectedLayerIndex: selectedLayerItem?.index,
      selectedLayerRecord,
      selectedPipelineRow,
    },
    commandState: {
      applyPreviewMp3Selection,
      deleteTemplatePending,
      handleDeleteTemplate,
      handleSelectBackground,
      handleSelectPreviewMp3,
      handleTemplateSelectionChange,
      handlePreviewLifecycleStateChange,
      openExportOutputFile,
      openExportOutputFolder,
      patchTemplatePending,
      saveOutputResolution,
      saveOutputResolutionPending,
      saveTemplatePending,
      saveWorkspaceTemplate,
      selectAndPlayPreviewMp3,
      startManualExport,
      startManualExportPending,
      startPipelineExport,
      startPipelineExportPending,
      stopPipelineExport,
      stopPipelineExportPending,
    },
    effectPackState: {
      backgroundEffectPackOptions: effectPackManager.background.options,
      backgroundEffectPackSelectionValue: effectPackManager.background.selectedValue,
      backgroundEffectPackStatus: effectPackManager.background.status,
      effectPackBusy: effectPackManager.spectrum.isBusy,
      logoEffectPackOptions: effectPackManager.logo.options,
      logoEffectPackSelectionValue: effectPackManager.logo.selectedValue,
      logoEffectPackStatus: effectPackManager.logo.status,
      particlesEffectPackOptions: effectPackManager.particles.options,
      particlesEffectPackSelectionValue: effectPackManager.particles.selectedValue,
      particlesEffectPackStatus: effectPackManager.particles.status,
      spectrumEffectPackOptions: effectPackManager.spectrum.options,
      spectrumEffectPackSelectionValue: effectPackManager.spectrum.selectedValue,
      spectrumEffectPackStatus: effectPackManager.spectrum.status,
    },
    effectPackCommandState: {
      activateBackgroundEffectPackVersion: effectPackManager.background.onActivateVersion,
      activateLogoEffectPackVersion: effectPackManager.logo.onActivateVersion,
      activateParticlesEffectPackVersion: effectPackManager.particles.onActivateVersion,
      activateSpectrumEffectPackVersion: effectPackManager.spectrum.onActivateVersion,
      applyBackgroundEffectPack: effectPackManager.background.onApply,
      applyLogoEffectPack: effectPackManager.logo.onApply,
      applyParticlesEffectPack: effectPackManager.particles.onApply,
      applySpectrumEffectPack: effectPackManager.spectrum.onApply,
      clearBackgroundEffectPack: effectPackManager.background.onClear,
      clearLogoEffectPack: effectPackManager.logo.onClear,
      clearParticlesEffectPack: effectPackManager.particles.onClear,
      clearSpectrumEffectPack: effectPackManager.spectrum.onClear,
      installEffectPack: effectPackManager.spectrum.onInstallFromFile,
      reloadEffectPacks: effectPackManager.spectrum.onReloadCatalog,
      removeBackgroundEffectPackVersion: effectPackManager.background.onRemoveVersion,
      removeLogoEffectPackVersion: effectPackManager.logo.onRemoveVersion,
      removeParticlesEffectPackVersion: effectPackManager.particles.onRemoveVersion,
      removeSpectrumEffectPackVersion: effectPackManager.spectrum.onRemoveVersion,
      toggleBackgroundEffectPackEnabled: effectPackManager.background.onToggleEnabled,
      toggleLogoEffectPackEnabled: effectPackManager.logo.onToggleEnabled,
      toggleParticlesEffectPackEnabled: effectPackManager.particles.onToggleEnabled,
      toggleSpectrumEffectPackEnabled: effectPackManager.spectrum.onToggleEnabled,
    },
    spectrumState: {
      applySpectrumPreset,
      flushSpectrumLayerCommit,
      handleAddLayer,
      handleDeleteLayer,
      handleDuplicateLayer,
      patchSelectedLayer,
      patchSelectedLayerColor,
      patchSpectrumDraft,
    },
    backgroundState: {
      patchBackgroundDraft,
      resetBackgroundTransform,
    },
    logoState: {
      applyLogoShape,
      applyLogoSize,
      patchLogoDraft,
      selectLogo,
      setSpectrumLogoGap,
      toggleSpectrumAttachment,
    },
    particlesState: {
      patchParticlesDraft,
    },
    textState: {
      addTextOverlay,
      applyTextAnchorAlignment,
      applyTextCase,
      applyTextPreset,
      deleteTextOverlay,
      duplicateTextOverlay,
      moveTextOverlay,
      selectedTextOverlay,
      selectedTextOverlayIndex,
      textOverlays,
      updateTextOverlay,
    },
    getTextAnchorAlignment,
  })

  return {
    isError,
    workspaceViewModel,
  }
}
