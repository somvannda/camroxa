import { useCallback } from 'react'

import type { VideoTemplateDraft } from '@/features/video/core/contracts/videoTemplateDraft'
import {
  applySpectrumLayerColorPatch,
  getSpectrumLayerColorFallback,
} from '@/features/video/domains/spectrum/spectrumColorEngine'
import { buildSpectrumPresetTemplate } from '@/features/video/domains/spectrum/spectrumStyleRegistry'
import type { SpectrumDraftSlice } from '@/features/video/workspace/templateDraftDomains'
import {
  cloneLayerRecords,
} from '@/features/video/workspace/videoWorkspaceDraftStore'

type UseSpectrumEditorOptions = {
  templateDraft: VideoTemplateDraft | null
  currentTemplate: Record<string, unknown>
  editableSpectrumLayers: Record<string, unknown>[]
  selectedLayerIndex: number
  setTemplateDraft: (draft: VideoTemplateDraft) => void
  setSpectrumLayersLive: (layers: Record<string, unknown>[]) => void
  setSelectedLayerKey: (key: string) => void
  emitStatus: (tone: 'success' | 'error', message: string) => void
  debugSend?: (payload: Record<string, unknown>) => void
}

export function useSpectrumEditor({
  templateDraft,
  currentTemplate,
  editableSpectrumLayers,
  selectedLayerIndex,
  setTemplateDraft,
  setSpectrumLayersLive,
  setSelectedLayerKey,
  emitStatus,
  debugSend,
}: UseSpectrumEditorOptions) {
  const commitSpectrumSessionDraft = useCallback(
    (nextDraft: VideoTemplateDraft, nextLayers = editableSpectrumLayers) => {
      setTemplateDraft(nextDraft)
      setSpectrumLayersLive(nextLayers)
    },
    [editableSpectrumLayers, setSpectrumLayersLive, setTemplateDraft],
  )

  const patchSpectrumDraft = useCallback(
    (patch: Partial<SpectrumDraftSlice>) => {
      if (!templateDraft) {
        return
      }
      commitSpectrumSessionDraft({ ...templateDraft, ...patch })
    },
    [commitSpectrumSessionDraft, templateDraft],
  )

  const flushSpectrumLayerCommit = useCallback(() => {
    return
  }, [])

  const commitSpectrumLayers = useCallback(
    (layers: Record<string, unknown>[], deferPersistence = false) => {
      setSpectrumLayersLive(layers)
      if (deferPersistence) {
        return
      }
    },
    [setSpectrumLayersLive],
  )

  const patchSelectedLayer = useCallback(
    (patch: Record<string, unknown>, deferPersistence = false) => {
      const layers = cloneLayerRecords(editableSpectrumLayers)
      if (!layers.length) {
        layers.push({})
      }
      const boundedIndex = Math.max(0, Math.min(layers.length - 1, selectedLayerIndex))
      const current = typeof layers[boundedIndex] === 'object' && layers[boundedIndex] !== null ? layers[boundedIndex] : {}
      layers[boundedIndex] = { ...(current as Record<string, unknown>), ...patch }
      commitSpectrumLayers(layers, deferPersistence)
    },
    [commitSpectrumLayers, editableSpectrumLayers, selectedLayerIndex],
  )

  const patchSelectedLayerColor = useCallback(
    (patch: Record<string, unknown>, deferPersistence = false) => {
      const layers = cloneLayerRecords(editableSpectrumLayers)
      if (!layers.length) {
        layers.push({})
      }
      const boundedIndex = Math.max(0, Math.min(layers.length - 1, selectedLayerIndex))
      const current =
        typeof layers[boundedIndex] === 'object' && layers[boundedIndex] !== null ? (layers[boundedIndex] as Record<string, unknown>) : {}
      layers[boundedIndex] = applySpectrumLayerColorPatch(
        current,
        patch,
        getSpectrumLayerColorFallback(boundedIndex),
      )
      commitSpectrumLayers(layers, deferPersistence)
    },
    [commitSpectrumLayers, editableSpectrumLayers, selectedLayerIndex],
  )

  const handleAddLayer = useCallback(() => {
    const layers = cloneLayerRecords(editableSpectrumLayers)
    const basis =
      typeof layers[selectedLayerIndex] === 'object' && layers[selectedLayerIndex] !== null
        ? (layers[selectedLayerIndex] as Record<string, unknown>)
        : {}
    const next = { ...basis, name: 'New Ring' }
    layers.push(next)
    commitSpectrumLayers(layers)
    setSelectedLayerKey(String(layers.length - 1))
  }, [commitSpectrumLayers, editableSpectrumLayers, selectedLayerIndex, setSelectedLayerKey])

  const handleDuplicateLayer = useCallback(() => {
    const layers = cloneLayerRecords(editableSpectrumLayers)
    const basis =
      typeof layers[selectedLayerIndex] === 'object' && layers[selectedLayerIndex] !== null
        ? (layers[selectedLayerIndex] as Record<string, unknown>)
        : {}
    const name = String(basis.name ?? '').trim()
    layers.push({ ...basis, name: name ? `${name} Copy` : 'Layer Copy' })
    commitSpectrumLayers(layers)
    setSelectedLayerKey(String(layers.length - 1))
  }, [commitSpectrumLayers, editableSpectrumLayers, selectedLayerIndex, setSelectedLayerKey])

  const handleDeleteLayer = useCallback(() => {
    const layers = cloneLayerRecords(editableSpectrumLayers)
    if (layers.length < 2) {
      return
    }
    const boundedIndex = Math.max(0, Math.min(layers.length - 1, selectedLayerIndex))
    layers.splice(boundedIndex, 1)
    commitSpectrumLayers(layers)
    setSelectedLayerKey(String(Math.max(0, boundedIndex - 1)))
  }, [commitSpectrumLayers, editableSpectrumLayers, selectedLayerIndex, setSelectedLayerKey])

  const applySpectrumPreset = useCallback(
    (presetKey: string) => {
      const normalizedPresetKey = String(presetKey || '').trim()
      if (!normalizedPresetKey) {
        return
      }
      debugSend?.({
        hypothesisId: 'C',
        location: 'useSpectrumEditor:applySpectrumPreset',
        msg: '[DEBUG] applying spectrum preset locally',
        data: {
          previousStyle: String(templateDraft?.style ?? ''),
          nextStyle: normalizedPresetKey,
        },
      })
      const patchedTemplate = buildSpectrumPresetTemplate(templateDraft ?? currentTemplate, normalizedPresetKey)
      if (!patchedTemplate) {
        emitStatus('error', 'Unable to apply that spectrum preset right now.')
        return
      }
      const nextDraft = templateDraft
        ? { ...templateDraft, style: String(patchedTemplate.style ?? templateDraft.style) }
        : null
      const nextLayers = cloneLayerRecords(patchedTemplate.layers)
      if (nextDraft) {
        commitSpectrumSessionDraft(nextDraft, nextLayers)
      }
      setSelectedLayerKey('0')
    },
    [commitSpectrumSessionDraft, currentTemplate, debugSend, emitStatus, setSelectedLayerKey, templateDraft],
  )

  return {
    applySpectrumPreset,
    commitSpectrumLayers,
    commitSpectrumSessionDraft,
    flushSpectrumLayerCommit,
    handleAddLayer,
    handleDeleteLayer,
    handleDuplicateLayer,
    patchSelectedLayer,
    patchSelectedLayerColor,
    patchSpectrumDraft,
    setSpectrumLayersLive,
  }
}
