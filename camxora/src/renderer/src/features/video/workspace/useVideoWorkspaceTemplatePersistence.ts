import { useCallback, useMemo } from 'react'

import { cloneLayerRecords } from '@/features/video/workspace/videoWorkspaceDraftStore'
import { buildVideoWorkspaceTemplateSavePatch } from '@/features/video/workspace/videoWorkspaceTemplateSave'
import { emitShellStatus } from '@/shared/lib/shellStatus'
import type { TemplateSettingsDraft } from '@/features/settings/settingsTemplateDraft'
import type { VideoWorkspaceDraftDirtyState } from '@/features/video/workspace/templateDraftDomains'

type UseVideoWorkspaceTemplatePersistenceOptions = {
  currentTemplate: Record<string, unknown>
  draftDirtyState: VideoWorkspaceDraftDirtyState
  editableSpectrumLayers: Record<string, unknown>[]
  templateDraft: TemplateSettingsDraft | null
  templateNameDirty: boolean
  templateNameDraft: string
  patchTemplate: (input: { patch: Record<string, unknown>; message: string; deferRefresh?: boolean }) => Promise<unknown>
}

export function useVideoWorkspaceTemplatePersistence({
  currentTemplate,
  draftDirtyState,
  editableSpectrumLayers,
  patchTemplate,
  templateDraft,
  templateNameDirty,
  templateNameDraft,
}: UseVideoWorkspaceTemplatePersistenceOptions) {
  const workspaceDirty = useMemo(
    () => templateNameDirty || Object.values(draftDirtyState).some(Boolean),
    [draftDirtyState, templateNameDirty],
  )

  const saveWorkspaceTemplate = useCallback(async () => {
    if (!templateDraft) {
      return
    }

    const nextTemplateName = templateNameDraft.trim()
    if (!nextTemplateName) {
      emitShellStatus({ tone: 'error', message: 'Template name is required before saving.' })
      return
    }

    await patchTemplate({
      patch: buildVideoWorkspaceTemplateSavePatch({
        template: currentTemplate,
        draft: templateDraft,
        templateName: nextTemplateName,
        layers: cloneLayerRecords(editableSpectrumLayers),
      }),
      message: 'Saved the current local workspace draft into the selected template.',
    })
  }, [currentTemplate, editableSpectrumLayers, patchTemplate, templateDraft, templateNameDraft])

  return {
    saveWorkspaceTemplate,
    workspaceDirty,
  }
}
