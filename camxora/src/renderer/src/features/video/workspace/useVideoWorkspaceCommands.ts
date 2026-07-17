import { useEffect, useRef } from 'react'
import { useMutation, type QueryClient } from '@tanstack/react-query'

import type { VideoTemplateDraft } from '@/features/video/core/contracts/videoTemplateDraft'
import {
  buildManualRenderSceneRequest,
  toVideoSerializableRenderSceneRequest,
} from '@/features/video/core/contracts/renderSceneRequest'
import type { DesktopApi, VideoWorkspaceState } from '@/shared/types/desktop'
import { apiConsumeLocalVideo, apiPatchSettings, type ProgressRowResponse } from '@/shared/api/platformEndpoints'
import type { ResolvedVideoPipelineInputs, VideoPipelineBranch } from '@/shared/lib/videoPipelineInputs'
import { emitShellStatus } from '@/shared/lib/shellStatus'
import { useBufferedTemplatePatch } from '@/features/video/workspace/useBufferedTemplatePatch'

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function mergeRecords(base: Record<string, unknown>, patch: Record<string, unknown>): Record<string, unknown> {
  const next: Record<string, unknown> = { ...base }
  Object.entries(patch).forEach(([key, value]) => {
    if (isRecord(value) && isRecord(next[key])) {
      next[key] = mergeRecords(next[key] as Record<string, unknown>, value)
      return
    }
    next[key] = value
  })
  return next
}

function getParentDirectory(targetPath: string): string {
  const normalized = String(targetPath || '').trim().replace(/[\\/]+$/, '')
  if (!normalized) {
    return ''
  }
  const slashIndex = Math.max(normalized.lastIndexOf('/'), normalized.lastIndexOf('\\'))
  if (slashIndex <= 0) {
    return normalized
  }
  return normalized.slice(0, slashIndex)
}

type UseVideoWorkspaceCommandsOptions = {
  desktopApi: DesktopApi
  queryClient: QueryClient
  workspace: VideoWorkspaceState | undefined
  resolvedPipelineInputs: ResolvedVideoPipelineInputs
  selectedPipelineBranch: VideoPipelineBranch
  selectedPipelineRow: ProgressRowResponse | null
  previewTemplate: Record<string, unknown>
  previewTrackPath: string
  previewPlayback: {
    isReady: boolean
    isLoading: boolean
  }
  issuePreviewPlaybackCommand: (command: { type: 'play' | 'pause' | 'stop' } | { type: 'seek'; timeSec: number }) => void
  queuePreviewAutoplay: (targetPath: string) => void
  setBackgroundPathDraft: (path: string) => void
  setSelectedTemplateId: (templateId: string) => void
  templateDraft: VideoTemplateDraft | null
  debugSend?: (payload: Record<string, unknown>) => void
  templateDraftStyle?: string
}

export function useVideoWorkspaceCommands({
  desktopApi,
  queryClient,
  workspace,
  resolvedPipelineInputs,
  selectedPipelineBranch,
  selectedPipelineRow,
  previewTemplate,
  previewTrackPath,
  previewPlayback,
  issuePreviewPlaybackCommand,
  queuePreviewAutoplay,
  setBackgroundPathDraft,
  setSelectedTemplateId,
  templateDraft,
  debugSend,
  templateDraftStyle,
}: UseVideoWorkspaceCommandsOptions) {
  const refreshWorkspace = async () => {
    await queryClient.invalidateQueries({ queryKey: ['video-workspace'] })
  }

  const saveTemplateMutation = useMutation({
    mutationFn: async (templateId: string) => desktopApi.video.setTemplate(templateId),
    onSuccess: async () => {
      emitShellStatus({ tone: 'success', message: 'Applied the selected template.' })
      await refreshWorkspace()
    },
    onError: (error) => {
      emitShellStatus({ tone: 'error', message: error instanceof Error ? error.message : 'Unable to change template right now.' })
    },
  })

  const deleteTemplateMutation = useMutation({
    mutationFn: async (templateId: string) => desktopApi.video.deleteTemplate(templateId),
    onSuccess: async (nextWorkspace, deletedTemplateId) => {
      const deletedTemplateName =
        workspace?.templates.find((template) => template.id === deletedTemplateId)?.name || 'the selected template'
      setSelectedTemplateId(nextWorkspace.templateId ?? '')
      queryClient.setQueryData(['video-workspace'], nextWorkspace)
      emitShellStatus({ tone: 'success', message: `Deleted ${deletedTemplateName}.` })
      await refreshWorkspace()
    },
    onError: (error) => {
      emitShellStatus({ tone: 'error', message: error instanceof Error ? error.message : 'Unable to delete the selected template right now.' })
    },
  })

  const saveOutputResolutionMutation = useMutation({
    mutationFn: async (resolution: string) =>
      apiPatchSettings({
        outputResolution: resolution,
        imageResolution: resolution,
      }),
    onSuccess: async () => {
      emitShellStatus({ tone: 'success', message: 'Output resolution updated.' })
      await refreshWorkspace()
    },
    onError: (error) => {
      emitShellStatus({ tone: 'error', message: error instanceof Error ? error.message : 'Unable to update output resolution right now.' })
    },
  })

  const refreshWorkspaceTimerRef = useRef<number | null>(null)

  useEffect(() => {
    return () => {
      if (refreshWorkspaceTimerRef.current != null) {
        window.clearTimeout(refreshWorkspaceTimerRef.current)
      }
    }
  }, [])

  const queueWorkspaceRefresh = (delayMs = 420) => {
    if (refreshWorkspaceTimerRef.current != null) {
      window.clearTimeout(refreshWorkspaceTimerRef.current)
    }
    refreshWorkspaceTimerRef.current = window.setTimeout(() => {
      refreshWorkspaceTimerRef.current = null
      void refreshWorkspace()
    }, delayMs)
  }

  const patchTemplateMutation = useMutation({
    mutationFn: async (input: { patch: Record<string, unknown>; message: string; deferRefresh?: boolean }) => {
      return desktopApi.video.patchTemplate(input.patch)
    },
    onSuccess: async (_result, input) => {
      if (input.message) {
        emitShellStatus({ tone: 'success', message: input.message })
      }
      if (input.deferRefresh) {
        queueWorkspaceRefresh()
        return
      }
      await refreshWorkspace()
    },
    onError: (error) => {
      emitShellStatus({
        tone: 'error',
        message: error instanceof Error ? error.message : 'Unable to save the selected template settings right now.',
      })
    },
  })

  const startPipelineExportMutation = useMutation({
    mutationFn: async () => {
      const trackCount = Math.max(1, workspace?.mp3List?.length || selectedPipelineRow?.meta?.expected || 1)
      const profileId = String(selectedPipelineRow?.meta?.profile_id || '').trim() || null
      await apiConsumeLocalVideo({
        operation_type: 'video',
        count: trackCount,
        channel_profile_id: profileId,
        ref_id: `video:${selectedPipelineRow?.meta.batch_id || ''}:${selectedPipelineRow?.meta.role || ''}:${selectedPipelineBranch}`,
      })
      let autoMerge = Boolean(workspace?.export?.autoMerge)
      if (autoMerge) {
        try {
          await apiConsumeLocalVideo({
            operation_type: 'video_merge',
            count: 1,
            channel_profile_id: profileId,
            ref_id: `video_merge:${selectedPipelineRow?.meta.batch_id || ''}:${selectedPipelineRow?.meta.role || ''}:${selectedPipelineBranch}`,
          })
        } catch (error) {
          autoMerge = false
          emitShellStatus({
            tone: 'error',
            message:
              error instanceof Error
                ? `Export will continue without merge: ${error.message}`
                : 'Export will continue without merge (billing).',
          })
        }
      }
      return desktopApi.video.startPipelineExport({
        runDir: resolvedPipelineInputs.runDir ?? '',
        backgroundPath: resolvedPipelineInputs.backgroundPath ?? '',
        branch: selectedPipelineBranch,
        batchId: selectedPipelineRow?.meta.batch_id ?? '',
        role: selectedPipelineRow?.meta.role ?? '',
        autoMerge,
      })
    },
    onSuccess: async () => {
      emitShellStatus({
        tone: 'success',
        message: `Started ${selectedPipelineBranch === 'long' ? 'long' : 'reel'} export from the selected pipeline run.`,
      })
      await refreshWorkspace()
    },
    onError: (error) => {
      emitShellStatus({ tone: 'error', message: error instanceof Error ? error.message : 'Unable to start the selected export right now.' })
    },
  })

  const startManualExportMutation = useMutation({
    mutationFn: async () => {
      if (!workspace || !templateDraft) {
        throw new Error('The live preview scene is not ready yet.')
      }

      const scene = buildManualRenderSceneRequest({
        template: previewTemplate,
        templateDraft,
        workspace,
        backgroundPath: workspace.backgroundPath,
        selectedMp3Path: previewTrackPath,
      })

      return desktopApi.video.startManualExport({
        scene: toVideoSerializableRenderSceneRequest(scene),
      })
    },
    onSuccess: async () => {
      emitShellStatus({
        tone: 'success',
        message: 'Queued manual export from the current live preview scene.',
      })
      await refreshWorkspace()
    },
    onError: (error) => {
      emitShellStatus({
        tone: 'error',
        message: error instanceof Error ? error.message : 'Unable to start manual export right now.',
      })
    },
  })

  const stopPipelineExportMutation = useMutation({
    mutationFn: async () => desktopApi.video.stopExport(),
    onSuccess: async () => {
      emitShellStatus({ tone: 'success', message: 'Requested stop for the active desktop export.' })
      await refreshWorkspace()
    },
    onError: (error) => {
      emitShellStatus({ tone: 'error', message: error instanceof Error ? error.message : 'Unable to stop the active export right now.' })
    },
  })

  const queueTemplatePatch = (patch: Record<string, unknown>) => {
    patchTemplateMutation.mutate({ patch, message: '', deferRefresh: true })
  }

  const queueTemplatePatchBuffered = useBufferedTemplatePatch({
    mergeRecords,
    flushPatch: (patch) => patchTemplateMutation.mutate({ patch, message: '', deferRefresh: true }),
    onPatchQueued: (patch) => {
      if ('style' in patch || 'layers' in patch) {
        debugSend?.({
          hypothesisId: 'B',
          location: 'useVideoWorkspaceCommands:queueTemplatePatchBuffered',
          msg: '[DEBUG] queued buffered spectrum patch',
          data: {
            localDraftStyle: String(templateDraftStyle ?? ''),
            patchStyle: typeof patch.style === 'string' ? patch.style : null,
            hasLayers: Array.isArray(patch.layers),
            patchKeys: Object.keys(patch),
          },
        })
      }
    },
  })

  const handleTemplateSelectionChange = (value: string) => {
    setSelectedTemplateId(value)
    if (!value || value === workspace?.templateId || saveTemplateMutation.isPending) {
      return
    }
    void saveTemplateMutation.mutateAsync(value)
  }

  const handleDeleteTemplate = async () => {
    const templateId = String(workspace?.templateId || '').trim()
    const templateName = String(workspace?.templateName || '').trim() || 'Untitled Template'
    if (!templateId || deleteTemplateMutation.isPending) {
      return
    }
    const isLastTemplate = (workspace?.templates.length ?? 0) <= 1
    const confirmed = window.confirm(
      isLastTemplate
        ? `Delete "${templateName}"? This will remove the last local video template and cannot be undone.`
        : `Delete "${templateName}"? This cannot be undone.`,
    )
    if (!confirmed) {
      return
    }
    await deleteTemplateMutation.mutateAsync(templateId)
  }

  const applyPreviewMp3Selection = async (targetPath: string) => {
    const nextWorkspace = await desktopApi.video.setMp3Path(targetPath)
    queryClient.setQueryData(['video-workspace'], nextWorkspace)
    return nextWorkspace
  }

  const selectAndPlayPreviewMp3 = async (targetPath: string) => {
    const trimmedTargetPath = String(targetPath || '').trim()
    if (!trimmedTargetPath) {
      return
    }

    if (trimmedTargetPath === previewTrackPath) {
      if (previewPlayback.isReady && !previewPlayback.isLoading) {
        issuePreviewPlaybackCommand({ type: 'play' })
        return
      }
      queuePreviewAutoplay(trimmedTargetPath)
      return
    }

    queuePreviewAutoplay(trimmedTargetPath)
    try {
      await applyPreviewMp3Selection(trimmedTargetPath)
    } catch (error) {
      queuePreviewAutoplay('')
      throw error
    }
  }

  const handleSelectPreviewMp3 = async () => {
    try {
      const selectedPath = await desktopApi.files.selectFile({
        title: 'Select preview MP3',
        filters: [{ name: 'Audio', extensions: ['mp3'] }],
      })
      if (!selectedPath) {
        return
      }
      await applyPreviewMp3Selection(selectedPath)
      emitShellStatus({ tone: 'success', message: 'Preview music updated.' })
    } catch (error) {
      emitShellStatus({ tone: 'error', message: error instanceof Error ? error.message : 'Unable to attach preview music right now.' })
    }
  }

  const handleSelectBackground = async () => {
    try {
      const selectedPath = await desktopApi.files.selectFile({
        title: 'Select background',
        filters: [{ name: 'Images', extensions: ['png', 'jpg', 'jpeg', 'webp'] }],
      })
      if (!selectedPath) {
        return
      }
      setBackgroundPathDraft(selectedPath)
      const nextWorkspace = await desktopApi.video.setBackgroundPath(selectedPath)
      queryClient.setQueryData(['video-workspace'], nextWorkspace)
      await apiPatchSettings({ videoRenderBackgroundPath: selectedPath })
      emitShellStatus({ tone: 'success', message: 'Background updated for the renderer preview.' })
    } catch (error) {
      emitShellStatus({ tone: 'error', message: error instanceof Error ? error.message : 'Unable to select a background right now.' })
    }
  }

  const openExportOutputFolder = async () => {
    const targetFolder =
      String(workspace?.export.outputDir || '').trim() ||
      getParentDirectory(String(workspace?.export.currentOutputPath || workspace?.export.lastOutputPath || '').trim())
    if (!targetFolder) {
      emitShellStatus({ tone: 'error', message: 'No export output folder is available yet.' })
      return
    }
    const opened = await desktopApi.files.openPath(targetFolder)
    if (!opened) {
      emitShellStatus({ tone: 'error', message: 'Unable to open the export output folder.' })
      return
    }
    emitShellStatus({ tone: 'success', message: 'Opened the export output folder.' })
  }

  const openExportOutputFile = async () => {
    const targetPath = String(workspace?.export.currentOutputPath || workspace?.export.lastOutputPath || '').trim()
    if (!targetPath) {
      emitShellStatus({ tone: 'error', message: 'No export output file is available yet.' })
      return
    }
    const opened = await desktopApi.files.openPath(targetPath)
    if (!opened) {
      emitShellStatus({ tone: 'error', message: 'Unable to open the export output file yet.' })
      return
    }
    emitShellStatus({ tone: 'success', message: 'Opened the export output file.' })
  }

  return {
    applyPreviewMp3Selection,
    handleSelectBackground,
    handleDeleteTemplate,
    openExportOutputFile,
    openExportOutputFolder,
    handleSelectPreviewMp3,
    handleTemplateSelectionChange,
    deleteTemplatePending: deleteTemplateMutation.isPending,
    patchTemplate: (input: { patch: Record<string, unknown>; message: string; deferRefresh?: boolean }) =>
      patchTemplateMutation.mutateAsync(input),
    patchTemplatePending: patchTemplateMutation.isPending,
    queueTemplatePatch,
    queueTemplatePatchBuffered,
    saveOutputResolution: (resolution: string) => saveOutputResolutionMutation.mutate(resolution),
    saveOutputResolutionPending: saveOutputResolutionMutation.isPending,
    saveTemplatePending: saveTemplateMutation.isPending,
    selectAndPlayPreviewMp3,
    startManualExport: () => startManualExportMutation.mutateAsync(),
    startManualExportPending: startManualExportMutation.isPending,
    startPipelineExport: () => startPipelineExportMutation.mutateAsync(),
    startPipelineExportPending: startPipelineExportMutation.isPending,
    stopPipelineExport: () => stopPipelineExportMutation.mutateAsync(),
    stopPipelineExportPending: stopPipelineExportMutation.isPending,
  }
}
