import { useCallback } from 'react'

import type { VideoTemplateDraft } from '@/features/video/core/contracts/videoTemplateDraft'
import type { BackgroundDraftSlice } from '@/features/video/workspace/templateDraftDomains'

type UseBackgroundEditorOptions = {
  templateDraft: VideoTemplateDraft | null
  setTemplateDraft: (draft: VideoTemplateDraft) => void
}

export function useBackgroundEditor({
  templateDraft,
  setTemplateDraft,
}: UseBackgroundEditorOptions) {
  const patchBackgroundDraft = useCallback(
    (patch: Partial<BackgroundDraftSlice>) => {
      if (!templateDraft) {
        return
      }
      const next: VideoTemplateDraft = { ...templateDraft, ...patch }
      setTemplateDraft(next)
    },
    [setTemplateDraft, templateDraft],
  )

  const resetBackgroundTransform = useCallback(() => {
    if (!templateDraft) {
      return
    }
    const nextDraft = { ...templateDraft, backgroundUserScale: 1 }
    setTemplateDraft(nextDraft)
  }, [setTemplateDraft, templateDraft])

  return {
    patchBackgroundDraft,
    resetBackgroundTransform,
  }
}
