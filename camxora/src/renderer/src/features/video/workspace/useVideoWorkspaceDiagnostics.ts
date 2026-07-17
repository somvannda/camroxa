import { useCallback, useEffect, useMemo, useState } from 'react'
import type { QueryClient } from '@tanstack/react-query'

import type { PreviewLifecycleState } from '@/features/video/preview/previewLifecycleState'
import type { PreviewPlaybackState } from '@/features/video/workspace/useVideoWorkspaceShell'
import type { VideoWorkspaceDraftDirtyState } from '@/features/video/workspace/templateDraftDomains'
import type { VideoPipelineBranch, ResolvedVideoPipelineInputs } from '@/shared/lib/videoPipelineInputs'
import type { ProgressRowResponse } from '@/shared/api/platformEndpoints'
import type { VideoWorkspaceState } from '@/shared/types/desktop'
import { emitShellStatus } from '@/shared/lib/shellStatus'

type DiagnosticsTone = 'neutral' | 'ready' | 'warning' | 'running'

type PreviewGuidance = {
  title: string
  detail: string
  items: string[]
  tone: DiagnosticsTone
  visible: boolean
}

export type VideoWorkspaceDiagnosticsState = {
  activeTabLabel: string
  branchLabel: string
  templateId: string
  templateName: string
  previewStatusLabel: string
  previewStatusMessage: string
  previewStatusTone: DiagnosticsTone
  previewGuidanceTitle: string
  previewGuidanceDetail: string
  previewGuidanceItems: string[]
  previewGuidanceTone: DiagnosticsTone
  previewNeedsAttention: boolean
  saveStatusLabel: string
  saveStatusTone: DiagnosticsTone
  exportStatusLabel: string
  exportStatusTone: DiagnosticsTone
  pipelineStatusLabel: string
  pipelineStatusTone: DiagnosticsTone
  previewSourceLabel: string
  selectedRunLabel: string
  backgroundLabel: string
  logoLabel: string
  trackLabel: string
  runDirectoryLabel: string
  dirtyDomains: Array<{ label: string; dirty: boolean }>
  canResetLocalDraft: boolean
  previewRuntimeNonce: number
  onCopyDiagnostics: () => Promise<void>
  onRefreshWorkspace: () => Promise<void>
  onRemountPreview: () => void
  onResetLocalDraft: () => void
}

type UseVideoWorkspaceDiagnosticsOptions = {
  activeTab: string
  backgroundPathDraft: string
  currentTemplate: Record<string, unknown>
  draftDirtyState: VideoWorkspaceDraftDirtyState
  patchTemplatePending: boolean
  previewLifecycleState: PreviewLifecycleState | null
  previewPlayback: PreviewPlaybackState
  previewTrackPath: string
  queryClient: QueryClient
  resetLocalDraft: () => void
  resolvedPipelineInputs: ResolvedVideoPipelineInputs
  saveTemplatePending: boolean
  selectedPipelineBranch: VideoPipelineBranch
  selectedPipelineRow: ProgressRowResponse | null
  templateNameDraft: string
  workspace: VideoWorkspaceState | undefined
  workspaceDirty: boolean
}

function formatPath(value: string | null | undefined, fallback: string): string {
  const trimmed = String(value || '').trim()
  return trimmed || fallback
}

function buildPreviewGuidance(options: {
  currentBackgroundPath: string
  previewLifecycleState: PreviewLifecycleState | null
  previewRemountPending: boolean
  previewTrackPath: string
  resolvedPipelineInputs: ResolvedVideoPipelineInputs
}): PreviewGuidance {
  const { currentBackgroundPath, previewLifecycleState, previewRemountPending, previewTrackPath, resolvedPipelineInputs } = options

  if (previewRemountPending) {
    return {
      title: 'Preview recovery in progress',
      detail: 'The renderer surface is remounting the WebGPU compositor after an explicit recovery action.',
      items: [
        'Wait a moment before judging the current frame output.',
        'Refresh Workspace if the stage context looks stale after recovery.',
        'Copy Diagnostics if repeated remounts are still required.',
      ],
      tone: 'running',
      visible: true,
    }
  }

  if (!previewLifecycleState) {
    return {
      title: '',
      detail: '',
      items: [],
      tone: 'neutral',
      visible: false,
    }
  }

  switch (previewLifecycleState.status) {
    case 'unsupported':
      return {
        title: 'Live GPU preview is unavailable on this machine',
        detail: previewLifecycleState.message,
        items: [
          'You can still edit the Video workspace, local draft, and export context without the live compositor.',
          'Move to a WebGPU-capable machine or runtime before trusting live GPU preview output.',
          'Copy Diagnostics only if this machine is expected to support WebGPU.',
        ],
        tone: 'warning',
        visible: true,
      }
    case 'device-lost':
      return {
        title: 'The preview surface lost its GPU device',
        detail: previewLifecycleState.message,
        items: [
          'Use Remount Preview first to rebuild the compositor surface.',
          'Refresh Workspace if the stage assets or run context look stale afterwards.',
          'Copy Diagnostics if device loss repeats on the same machine.',
        ],
        tone: 'warning',
        visible: true,
      }
    case 'error':
      return {
        title: 'The renderer preview failed to start cleanly',
        detail: previewLifecycleState.message,
        items: [
          'Use Remount Preview to retry the compositor startup.',
          'Refresh Workspace if the preview assets were changed immediately before the failure.',
          'Copy Diagnostics when the same startup error keeps returning.',
        ],
        tone: 'warning',
        visible: true,
      }
    case 'recovering':
      return {
        title: 'Preview recovery is still underway',
        detail: previewLifecycleState.message,
        items: [
          'Let the compositor finish reinitializing before validating the frame output.',
          'Use Refresh Workspace if the selected run or assets do not match the current shell state.',
          'Copy Diagnostics if the recovery state never resolves.',
        ],
        tone: 'running',
        visible: true,
      }
    case 'initializing':
      return {
        title: 'Preview startup is still in progress',
        detail: previewLifecycleState.message,
        items: [
          'Wait for the compositor to finish initializing before checking fine visual details.',
          'The shell is still editable while the renderer brings the preview surface online.',
        ],
        tone: 'running',
        visible: true,
      }
    case 'fallback-active': {
      const items = [
        'Edits still apply to the local workspace draft while the default fallback scene is active.',
      ]
      if (!currentBackgroundPath.trim()) {
        items.push('Select a background to replace the default fallback scene with real artwork.')
      }
      if (!previewTrackPath.trim()) {
        items.push('Select a preview MP3 so the stage can validate audio-reactive motion against a real track.')
      }
      if (!resolvedPipelineInputs.ready) {
        items.push('Choose a pipeline run when you need export-ready branch context under the preview.')
      }
      return {
        title: 'Preview is running in degraded fallback mode',
        detail: previewLifecycleState.message,
        items,
        tone: 'warning',
        visible: true,
      }
    }
    case 'running':
    default:
      return {
        title: '',
        detail: '',
        items: [],
        tone: 'ready',
        visible: false,
      }
  }
}

export function useVideoWorkspaceDiagnostics({
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
  workspace,
  workspaceDirty,
}: UseVideoWorkspaceDiagnosticsOptions): VideoWorkspaceDiagnosticsState {
  const [previewRuntimeNonce, setPreviewRuntimeNonce] = useState(0)
  const [previewRemountPending, setPreviewRemountPending] = useState(false)

  const branchLabel = selectedPipelineBranch === 'long' ? 'Long 16:9' : 'Reel 9:16'
  const selectedRunLabel = selectedPipelineRow
    ? `${selectedPipelineRow.channel} - ${selectedPipelineRow.run_date} - ${String(selectedPipelineRow.meta.role).toUpperCase()}`
    : 'No pipeline run selected'

  const currentBackgroundPath =
    backgroundPathDraft || workspace?.backgroundPath || resolvedPipelineInputs.backgroundPath || ''
  const currentLogoPath = String(currentTemplate.logoPath ?? workspace?.logoPath ?? '').trim()
  const previewSourceLabel = String(workspace?.ui.source ?? 'renderer').replace(/-/g, ' ')

  useEffect(() => {
    if (!previewLifecycleState) {
      return
    }
    if (
      previewLifecycleState.status === 'running' ||
      previewLifecycleState.status === 'fallback-active' ||
      previewLifecycleState.status === 'unsupported' ||
      previewLifecycleState.status === 'device-lost' ||
      previewLifecycleState.status === 'error'
    ) {
      setPreviewRemountPending(false)
    }
  }, [previewLifecycleState])

  const previewStatus = useMemo(() => {
    if (previewRemountPending) {
      return {
        label: 'Preview Recovering',
        message: 'Renderer preview is remounting the WebGPU compositor.',
        tone: 'running' as const,
      }
    }
    if (previewLifecycleState) {
      const tone: DiagnosticsTone =
        previewLifecycleState.status === 'running'
          ? 'ready'
          : previewLifecycleState.status === 'fallback-active'
            ? 'warning'
            : previewLifecycleState.status === 'initializing' || previewLifecycleState.status === 'recovering'
              ? 'running'
              : previewLifecycleState.status === 'unsupported'
                ? 'warning'
                : previewLifecycleState.status === 'device-lost' || previewLifecycleState.status === 'error'
                  ? 'warning'
                  : 'neutral'
      return {
        label: previewLifecycleState.label,
        message: previewLifecycleState.message,
        tone,
      }
    }
    if (!previewTrackPath.trim()) {
      return { label: 'No Preview Track', message: 'Select a track to drive the renderer preview transport.', tone: 'neutral' as const }
    }
    if (previewPlayback.isLoading) {
      return { label: 'Preview Loading', message: 'Preview transport is loading the selected track.', tone: 'running' as const }
    }
    if (previewPlayback.isPlaying) {
      return { label: 'Preview Playing', message: 'Preview playback is active.', tone: 'running' as const }
    }
    if (previewPlayback.isReady) {
      return { label: 'Preview Ready', message: 'Preview transport is ready.', tone: 'ready' as const }
    }
    return { label: 'Preview Waiting', message: 'Preview transport is waiting for a valid track.', tone: 'warning' as const }
  }, [previewLifecycleState, previewPlayback.isLoading, previewPlayback.isPlaying, previewPlayback.isReady, previewRemountPending, previewTrackPath])

  const previewGuidance = useMemo(
    () =>
      buildPreviewGuidance({
        currentBackgroundPath,
        previewLifecycleState,
        previewRemountPending,
        previewTrackPath,
        resolvedPipelineInputs,
      }),
    [currentBackgroundPath, previewLifecycleState, previewRemountPending, previewTrackPath, resolvedPipelineInputs],
  )

  const saveStatus = useMemo(() => {
    if (patchTemplatePending || saveTemplatePending) {
      return { label: 'Save In Flight', tone: 'running' as const }
    }
    if (workspaceDirty) {
      return { label: 'Local Draft Pending', tone: 'warning' as const }
    }
    return { label: 'Template Synced', tone: 'ready' as const }
  }, [patchTemplatePending, saveTemplatePending, workspaceDirty])

  const exportStatus = useMemo(() => {
    if (workspace?.export.running) {
      return { label: 'Export Running', tone: 'running' as const }
    }
    if (resolvedPipelineInputs.ready) {
      return { label: 'Export Ready', tone: 'ready' as const }
    }
    if (selectedPipelineRow) {
      return { label: 'Missing Export Inputs', tone: 'warning' as const }
    }
    return { label: 'No Export Run', tone: 'neutral' as const }
  }, [resolvedPipelineInputs.ready, selectedPipelineRow, workspace?.export.running])

  const pipelineStatus = useMemo(() => {
    if (resolvedPipelineInputs.ready) {
      return { label: 'Branch Inputs Ready', tone: 'ready' as const }
    }
    if (selectedPipelineRow) {
      return { label: 'Branch Inputs Missing', tone: 'warning' as const }
    }
    return { label: 'No Pipeline Inputs', tone: 'neutral' as const }
  }, [resolvedPipelineInputs.ready, selectedPipelineRow])

  const dirtyDomains = useMemo(
    () => [
      { label: 'Template', dirty: workspaceDirty },
      { label: 'Spectrum', dirty: draftDirtyState.spectrum },
      { label: 'Background', dirty: draftDirtyState.background },
      { label: 'Logo', dirty: draftDirtyState.logo },
      { label: 'Particles', dirty: draftDirtyState.particles },
      { label: 'Text', dirty: draftDirtyState.text },
    ],
    [draftDirtyState, workspaceDirty],
  )

  const diagnosticsPayload = useMemo(
    () => ({
      generatedAt: new Date().toISOString(),
      videoWorkspace: {
        activeTab,
        branch: selectedPipelineBranch,
        templateId: String(workspace?.templateId ?? ''),
        templateName: templateNameDraft.trim(),
        previewRuntimeNonce,
        previewSource: workspace?.ui.source ?? 'renderer',
        preview: {
          status: previewStatus.label,
          message: previewStatus.message,
          guidance: previewGuidance.visible
            ? {
                title: previewGuidance.title,
                detail: previewGuidance.detail,
                items: previewGuidance.items,
                tone: previewGuidance.tone,
              }
            : null,
          lifecycleStatus: previewLifecycleState?.status ?? null,
          playback: previewPlayback,
          trackPath: previewTrackPath,
          backgroundPath: currentBackgroundPath || null,
          logoPath: currentLogoPath || null,
          aspectRatio: workspace?.previewAspectRatio ?? null,
        },
        save: {
          status: saveStatus.label,
          workspaceDirty,
          draftDirtyState,
        },
        export: {
          status: exportStatus.label,
          running: workspace?.export.running ?? false,
          currentStatus: workspace?.export.currentStatus ?? 'idle',
          branch: workspace?.export.branch ?? null,
          lastOutputPath: workspace?.export.lastOutputPath ?? null,
          lastMergedOutputPath: workspace?.export.lastMergedOutputPath ?? null,
        },
        pipeline: {
          status: pipelineStatus.label,
          selectedRunLabel,
          resolvedInputs: resolvedPipelineInputs,
          selectedRowMeta: selectedPipelineRow?.meta ?? null,
        },
      },
    }),
    [
      activeTab,
      currentBackgroundPath,
      currentLogoPath,
      draftDirtyState,
      exportStatus.label,
      pipelineStatus.label,
      previewPlayback,
      previewLifecycleState?.status,
      previewGuidance.detail,
      previewGuidance.items,
      previewGuidance.title,
      previewGuidance.tone,
      previewGuidance.visible,
      previewRuntimeNonce,
      previewStatus.label,
      previewStatus.message,
      previewTrackPath,
      resolvedPipelineInputs,
      saveStatus.label,
      selectedPipelineBranch,
      selectedPipelineRow?.meta,
      selectedRunLabel,
      templateNameDraft,
      workspace?.export.branch,
      workspace?.export.currentStatus,
      workspace?.export.lastMergedOutputPath,
      workspace?.export.lastOutputPath,
      workspace?.export.running,
      workspace?.previewAspectRatio,
      workspace?.templateId,
      workspace?.ui.source,
      workspaceDirty,
    ],
  )

  const onRefreshWorkspace = useCallback(async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['video-workspace'] }),
      queryClient.invalidateQueries({ queryKey: ['progress-rows'] }),
      queryClient.invalidateQueries({ queryKey: ['shared-profiles'] }),
    ])
    emitShellStatus({ tone: 'success', message: 'Video workspace diagnostics refreshed.' })
  }, [queryClient])

  const onRemountPreview = useCallback(() => {
    setPreviewRemountPending(true)
    setPreviewRuntimeNonce((current) => current + 1)
    emitShellStatus({ tone: 'success', message: 'Remounted the renderer preview surface.' })
  }, [])

  const onResetLocalDraft = useCallback(() => {
    resetLocalDraft()
    emitShellStatus({ tone: 'success', message: 'Reset the local Video workspace draft back to the saved template.' })
  }, [resetLocalDraft])

  const onCopyDiagnostics = useCallback(async () => {
    const payload = JSON.stringify(diagnosticsPayload, null, 2)
    try {
      if (typeof navigator === 'undefined' || !navigator.clipboard?.writeText) {
        throw new Error('Clipboard access is not available in this environment.')
      }
      await navigator.clipboard.writeText(payload)
      emitShellStatus({ tone: 'success', message: 'Copied Video diagnostics to the clipboard.' })
    } catch (error) {
      emitShellStatus({
        tone: 'error',
        message: error instanceof Error ? error.message : 'Unable to copy Video diagnostics right now.',
      })
    }
  }, [diagnosticsPayload])

  return {
    activeTabLabel: activeTab,
    backgroundLabel: formatPath(currentBackgroundPath, 'No background attached'),
    branchLabel,
    canResetLocalDraft: workspaceDirty,
    dirtyDomains,
    exportStatusLabel: exportStatus.label,
    exportStatusTone: exportStatus.tone,
    logoLabel: formatPath(currentLogoPath, 'No logo attached'),
    onCopyDiagnostics,
    onRefreshWorkspace,
    onRemountPreview,
    onResetLocalDraft,
    pipelineStatusLabel: pipelineStatus.label,
    pipelineStatusTone: pipelineStatus.tone,
    previewRuntimeNonce,
    previewStatusMessage: previewStatus.message,
    previewSourceLabel,
    previewGuidanceDetail: previewGuidance.detail,
    previewGuidanceItems: previewGuidance.items,
    previewGuidanceTitle: previewGuidance.title,
    previewGuidanceTone: previewGuidance.tone,
    previewNeedsAttention: previewGuidance.visible,
    previewStatusLabel: previewStatus.label,
    previewStatusTone: previewStatus.tone,
    runDirectoryLabel: formatPath(resolvedPipelineInputs.runDir, 'No run directory resolved'),
    saveStatusLabel: saveStatus.label,
    saveStatusTone: saveStatus.tone,
    selectedRunLabel,
    templateId: String(workspace?.templateId ?? ''),
    templateName: templateNameDraft.trim() || String(workspace?.templateName ?? '').trim() || 'Untitled',
    trackLabel: formatPath(previewTrackPath, 'No preview track attached'),
  }
}
