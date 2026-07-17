import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import {
  buildTemplateDraft,
  type TemplateSettingsDraft,
} from '@/features/settings/settingsTemplateDraft'
import {
  clearVideoWorkspaceDraftSnapshot,
  cloneLayerRecords,
  readVideoWorkspaceDraftSnapshot,
  writeVideoWorkspaceDraftSnapshot,
} from '@/features/video/workspace/videoWorkspaceDraftStore'
import {
  buildVideoWorkspaceDraftDirtyState,
  buildVideoWorkspaceDraftSlices,
  pickSpectrumDraftSlice,
} from '@/features/video/workspace/templateDraftDomains'
import type { VideoWorkspaceState } from '@/shared/types/desktop'

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

type UseVideoWorkspaceDraftOptions = {
  workspace: VideoWorkspaceState | undefined
  storagePrefix: string
  debugSend?: (payload: Record<string, unknown>) => void
  onHydrated?: () => void
}

export function useVideoWorkspaceDraft({
  workspace,
  storagePrefix,
  debugSend,
  onHydrated,
}: UseVideoWorkspaceDraftOptions) {
  const [templateDraft, setTemplateDraft] = useState<TemplateSettingsDraft | null>(null)
  const [templateNameDraft, setTemplateNameDraft] = useState('')
  const [localSpectrumLayers, setLocalSpectrumLayers] = useState<Record<string, unknown>[] | null>(null)
  const templateDraftRef = useRef<TemplateSettingsDraft | null>(null)
  const templateNameDraftRef = useRef('')
  const localSpectrumLayersRef = useRef<Record<string, unknown>[] | null>(null)
  const hydratedTemplateIdRef = useRef('')

  const currentTemplate = useMemo(
    () => (isRecord(workspace?.template) ? workspace.template : {}),
    [workspace?.template],
  )

  const persistedDraft = useMemo(() => {
    if (!workspace) {
      return null
    }
    return buildTemplateDraft(currentTemplate, workspace)
  }, [currentTemplate, workspace])

  const editableSpectrumLayers = useMemo(
    () => localSpectrumLayers ?? cloneLayerRecords(currentTemplate.layers),
    [currentTemplate.layers, localSpectrumLayers],
  )

  const persistedSpectrumSnapshot = useMemo(() => {
    if (!persistedDraft) {
      return ''
    }
    return JSON.stringify({
      spectrum: pickSpectrumDraftSlice(persistedDraft),
      layers: cloneLayerRecords(currentTemplate.layers),
    })
  }, [currentTemplate.layers, persistedDraft])

  const localSpectrumSnapshot = useMemo(() => {
    if (!templateDraft) {
      return ''
    }
    return JSON.stringify({
      spectrum: pickSpectrumDraftSlice(templateDraft),
      layers: editableSpectrumLayers,
    })
  }, [editableSpectrumLayers, templateDraft])

  const spectrumSessionDirty = Boolean(localSpectrumSnapshot && localSpectrumSnapshot !== persistedSpectrumSnapshot)
  const templateNameDirty = templateNameDraft.trim() !== String(workspace?.templateName ?? '').trim()

  const draftSlices = useMemo(
    () => (templateDraft ? buildVideoWorkspaceDraftSlices(templateDraft) : null),
    [templateDraft],
  )

  const draftDirtyState = useMemo(
    () => buildVideoWorkspaceDraftDirtyState(templateDraft, persistedDraft, { spectrumDirty: spectrumSessionDirty }),
    [persistedDraft, spectrumSessionDirty, templateDraft],
  )

  const persistLocalDraft = useCallback(
    (
      nextDraft: TemplateSettingsDraft | null,
      nextTemplateName: string,
      nextLayers: Record<string, unknown>[] | null,
      templateId: string,
    ) => {
      if (!nextDraft || !templateId) {
        return
      }
      writeVideoWorkspaceDraftSnapshot(storagePrefix, templateId, {
        draft: nextDraft,
        layers: cloneLayerRecords(nextLayers ?? currentTemplate.layers),
        templateName: nextTemplateName,
      })
    },
    [currentTemplate.layers, storagePrefix],
  )

  const setSpectrumLayersLive = useCallback(
    (layers: Record<string, unknown>[]) => {
      const nextLayers = cloneLayerRecords(layers)
      localSpectrumLayersRef.current = nextLayers
      setLocalSpectrumLayers(nextLayers)
      persistLocalDraft(
        templateDraftRef.current,
        templateNameDraftRef.current,
        nextLayers,
        hydratedTemplateIdRef.current,
      )
    },
    [persistLocalDraft],
  )

  const setTemplateDraftLive = useCallback(
    (draft: TemplateSettingsDraft) => {
      templateDraftRef.current = draft
      setTemplateDraft(draft)
      persistLocalDraft(
        draft,
        templateNameDraftRef.current,
        localSpectrumLayersRef.current,
        hydratedTemplateIdRef.current,
      )
    },
    [persistLocalDraft],
  )

  const setTemplateNameDraftLive = useCallback(
    (value: string) => {
      templateNameDraftRef.current = value
      setTemplateNameDraft(value)
      persistLocalDraft(
        templateDraftRef.current,
        value,
        localSpectrumLayersRef.current,
        hydratedTemplateIdRef.current,
      )
    },
    [persistLocalDraft],
  )

  const resetLocalDraft = useCallback(() => {
    if (!workspace || !persistedDraft) {
      return
    }

    const templateId = String(workspace.templateId ?? '')
    const restoredTemplateName = String(workspace.templateName ?? '')
    const restoredLayers = cloneLayerRecords(currentTemplate.layers)

    clearVideoWorkspaceDraftSnapshot(storagePrefix, templateId)
    hydratedTemplateIdRef.current = templateId
    templateDraftRef.current = persistedDraft
    templateNameDraftRef.current = restoredTemplateName
    setTemplateDraft(persistedDraft)
    setTemplateNameDraft(restoredTemplateName)
    localSpectrumLayersRef.current = restoredLayers
    setLocalSpectrumLayers(restoredLayers)
    onHydrated?.()
  }, [currentTemplate.layers, onHydrated, persistedDraft, storagePrefix, workspace])

  useEffect(() => {
    if (!workspace) {
      return
    }
    const incomingTemplateId = String(workspace.templateId ?? '')
    const shouldHydrateDraft = !templateDraft || hydratedTemplateIdRef.current !== incomingTemplateId
    debugSend?.({
      hypothesisId: 'A',
      location: 'useVideoWorkspaceDraft:workspace-hydration',
      msg: shouldHydrateDraft
        ? '[DEBUG] hydrating templateDraft from workspace data'
        : '[DEBUG] skipped workspace hydration to preserve local draft',
      data: {
        shouldHydrateDraft,
        incomingTemplateStyle: String(currentTemplate.style ?? ''),
        localDraftStyleBeforeHydrate: String(templateDraft?.style ?? ''),
        incomingTemplateId,
        templateName: String(workspace.templateName ?? ''),
      },
    })
    if (!shouldHydrateDraft) {
      return
    }

    const nextTemplateDraft = buildTemplateDraft(currentTemplate, workspace)
    const workspaceSnapshot = readVideoWorkspaceDraftSnapshot(
      storagePrefix,
      incomingTemplateId,
      nextTemplateDraft,
      String(workspace.templateName ?? ''),
    )
    const restoredTemplateDraft = workspaceSnapshot?.draft ?? nextTemplateDraft
    const restoredLayers =
      workspaceSnapshot?.layers.length
      ? cloneLayerRecords(workspaceSnapshot.layers)
      : cloneLayerRecords(currentTemplate.layers)
    const restoredTemplateName = workspaceSnapshot?.templateName ?? String(workspace.templateName ?? '')

    hydratedTemplateIdRef.current = incomingTemplateId
    templateDraftRef.current = restoredTemplateDraft
    templateNameDraftRef.current = restoredTemplateName
    setTemplateDraft(restoredTemplateDraft)
    setTemplateNameDraft(restoredTemplateName)
    localSpectrumLayersRef.current = restoredLayers
    setLocalSpectrumLayers(restoredLayers)
    onHydrated?.()
  }, [currentTemplate, debugSend, onHydrated, storagePrefix, templateDraft, workspace])

  return {
    currentTemplate,
    draftDirtyState,
    draftSlices,
    editableSpectrumLayers,
    persistedDraft,
    setSpectrumLayersLive,
    setTemplateDraft: setTemplateDraftLive,
    setTemplateNameDraft: setTemplateNameDraftLive,
    resetLocalDraft,
    spectrumSessionDirty,
    templateNameDirty,
    templateDraft,
    templateNameDraft,
  }
}
