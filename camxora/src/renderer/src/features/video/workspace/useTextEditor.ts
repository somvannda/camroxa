import { useCallback } from 'react'

import {
  buildDefaultTextOverlayDraft,
  type TemplateSettingsDraft,
  type TemplateTextOverlayDraft,
} from '@/features/settings/settingsTemplateDraft'
import { buildTextPresetStyle } from '@/features/video/workspace/textOverlayPresets'

export type VideoSidePanelTabId = 'text' | 'animation' | 'export'

type UseTextEditorOptions = {
  templateDraft: TemplateSettingsDraft | null
  selectedTextOverlayKey: string
  setTemplateDraft: (draft: TemplateSettingsDraft) => void
  setSelectedTextOverlayKey: (key: string) => void
  setSidePanelTab: (tab: VideoSidePanelTabId) => void
}

export function getTextAnchorAlignment(anchor: string): 'left' | 'center' | 'right' {
  if (anchor.endsWith('left')) {
    return 'left'
  }
  if (anchor.endsWith('right')) {
    return 'right'
  }
  return 'center'
}

export function useTextEditor({
  templateDraft,
  selectedTextOverlayKey,
  setTemplateDraft,
  setSelectedTextOverlayKey,
  setSidePanelTab,
}: UseTextEditorOptions) {
  const textOverlays = templateDraft?.textOverlays ?? []
  const selectedTextOverlayIndexRaw = Number(selectedTextOverlayKey)
  const selectedTextOverlayIndex =
    textOverlays.length && Number.isFinite(selectedTextOverlayIndexRaw)
      ? Math.max(0, Math.min(textOverlays.length - 1, selectedTextOverlayIndexRaw))
      : 0
  const selectedTextOverlay = textOverlays[selectedTextOverlayIndex] ?? null

  const commitTextDraft = useCallback(
    (next: TemplateSettingsDraft) => {
      setTemplateDraft(next)
    },
    [setTemplateDraft],
  )

  const updateTextOverlay = useCallback(
    (index: number, nextOverlay: TemplateTextOverlayDraft) => {
      if (!templateDraft) {
        return
      }
      commitTextDraft({
        ...templateDraft,
        textOverlays: textOverlays.map((item, itemIndex) => (itemIndex === index ? nextOverlay : item)),
      })
    },
    [commitTextDraft, templateDraft, textOverlays],
  )

  const addTextOverlay = useCallback(() => {
    if (!templateDraft) {
      return
    }
    const nextOverlays = [...textOverlays, buildDefaultTextOverlayDraft()]
    commitTextDraft({ ...templateDraft, textOverlays: nextOverlays })
    setSelectedTextOverlayKey(String(Math.max(0, nextOverlays.length - 1)))
    setSidePanelTab('text')
  }, [commitTextDraft, setSelectedTextOverlayKey, setSidePanelTab, templateDraft, textOverlays])

  const applyTextPreset = useCallback(
    (preset: string) => {
      if (!templateDraft) {
        return
      }
      if (preset === 'neon_brush_stack') {
        const nextOverlays = [
          ...textOverlays,
          {
            ...buildDefaultTextOverlayDraft(),
            enabled: true,
            text: 'TEXT 1',
            anchor: 'top-center',
            x: 0,
            y: 70,
            fontSize: 120,
            color: '#ffffff',
            strokeColor: '#38bdf8',
            strokeWidth: 3,
            shadow: 0.55,
            animation: 'pop',
          },
          {
            ...buildDefaultTextOverlayDraft(),
            enabled: true,
            text: 'TEXT 2',
            anchor: 'top-center',
            x: 0,
            y: 200,
            fontSize: 86,
            color: '#ff4fd8',
            strokeColor: '#0b1220',
            strokeWidth: 2.5,
            shadow: 0.45,
            animation: 'slide_right',
          },
          {
            ...buildDefaultTextOverlayDraft(),
            enabled: true,
            text: '2026',
            anchor: 'top-center',
            x: 0,
            y: 310,
            fontSize: 74,
            color: '#b6c3ff',
            strokeColor: '#0b1220',
            strokeWidth: 2.2,
            shadow: 0.35,
            animation: 'fade',
          },
        ]
        commitTextDraft({ ...templateDraft, textOverlays: nextOverlays })
        setSelectedTextOverlayKey(String(Math.max(0, nextOverlays.length - 1)))
        setSidePanelTab('text')
        return
      }

      const style = buildTextPresetStyle(preset)
      if (!style) {
        return
      }

      if (selectedTextOverlay) {
        updateTextOverlay(selectedTextOverlayIndex, { ...selectedTextOverlay, ...style })
        setSidePanelTab('text')
        return
      }

      const nextOverlay: TemplateTextOverlayDraft = {
        ...buildDefaultTextOverlayDraft(),
        enabled: true,
        ...style,
      }
      const nextOverlays = [...textOverlays, nextOverlay]
      commitTextDraft({ ...templateDraft, textOverlays: nextOverlays })
      setSelectedTextOverlayKey(String(Math.max(0, nextOverlays.length - 1)))
      setSidePanelTab('text')
    },
    [
      commitTextDraft,
      selectedTextOverlay,
      selectedTextOverlayIndex,
      setSelectedTextOverlayKey,
      setSidePanelTab,
      templateDraft,
      textOverlays,
      updateTextOverlay,
    ],
  )

  const duplicateTextOverlay = useCallback(() => {
    if (!templateDraft || !selectedTextOverlay) {
      return
    }
    const nextOverlays = [
      ...textOverlays.slice(0, selectedTextOverlayIndex + 1),
      { ...selectedTextOverlay },
      ...textOverlays.slice(selectedTextOverlayIndex + 1),
    ]
    commitTextDraft({ ...templateDraft, textOverlays: nextOverlays })
    setSelectedTextOverlayKey(String(selectedTextOverlayIndex + 1))
  }, [
    commitTextDraft,
    selectedTextOverlay,
    selectedTextOverlayIndex,
    setSelectedTextOverlayKey,
    templateDraft,
    textOverlays,
  ])

  const deleteTextOverlay = useCallback(() => {
    if (!templateDraft || !selectedTextOverlay) {
      return
    }
    const nextOverlays = textOverlays.filter((_, index) => index !== selectedTextOverlayIndex)
    commitTextDraft({ ...templateDraft, textOverlays: nextOverlays })
    setSelectedTextOverlayKey(String(Math.max(0, Math.min(selectedTextOverlayIndex, nextOverlays.length - 1))))
  }, [
    commitTextDraft,
    selectedTextOverlay,
    selectedTextOverlayIndex,
    setSelectedTextOverlayKey,
    templateDraft,
    textOverlays,
  ])

  const moveTextOverlay = useCallback(
    (direction: -1 | 1) => {
      if (!templateDraft || !selectedTextOverlay) {
        return
      }
      const nextIndex = selectedTextOverlayIndex + direction
      if (nextIndex < 0 || nextIndex >= textOverlays.length) {
        return
      }
      const nextOverlays = textOverlays.slice()
      const temp = nextOverlays[selectedTextOverlayIndex]
      nextOverlays[selectedTextOverlayIndex] = nextOverlays[nextIndex]
      nextOverlays[nextIndex] = temp
      commitTextDraft({ ...templateDraft, textOverlays: nextOverlays })
      setSelectedTextOverlayKey(String(nextIndex))
    },
    [
      commitTextDraft,
      selectedTextOverlay,
      selectedTextOverlayIndex,
      setSelectedTextOverlayKey,
      templateDraft,
      textOverlays,
    ],
  )

  const applyTextCase = useCallback(
    (mode: 'upper' | 'lower' | 'title') => {
      if (!selectedTextOverlay) {
        return
      }
      const currentText = selectedTextOverlay.text
      const nextText =
        mode === 'upper'
          ? currentText.toUpperCase()
          : mode === 'lower'
            ? currentText.toLowerCase()
            : currentText.replace(/\w\S*/g, (word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
      updateTextOverlay(selectedTextOverlayIndex, { ...selectedTextOverlay, text: nextText })
    },
    [selectedTextOverlay, selectedTextOverlayIndex, updateTextOverlay],
  )

  const applyTextAnchorAlignment = useCallback(
    (alignment: 'left' | 'center' | 'right') => {
      if (!selectedTextOverlay) {
        return
      }
      const currentAnchor = selectedTextOverlay.anchor
      const vertical = currentAnchor.startsWith('top')
        ? 'top'
        : currentAnchor.startsWith('bottom')
          ? 'bottom'
          : 'center'
      const nextAnchor =
        vertical === 'center'
          ? alignment === 'center'
            ? 'center'
            : alignment === 'left'
              ? 'bottom-left'
              : 'bottom-right'
          : `${vertical}-${alignment}`
      updateTextOverlay(selectedTextOverlayIndex, { ...selectedTextOverlay, anchor: nextAnchor })
    },
    [selectedTextOverlay, selectedTextOverlayIndex, updateTextOverlay],
  )

  return {
    addTextOverlay,
    applyTextAnchorAlignment,
    applyTextCase,
    applyTextPreset,
    commitTextDraft,
    deleteTextOverlay,
    duplicateTextOverlay,
    moveTextOverlay,
    selectedTextOverlay,
    selectedTextOverlayIndex,
    textOverlays,
    updateTextOverlay,
  }
}
