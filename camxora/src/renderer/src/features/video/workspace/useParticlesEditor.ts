import { useCallback } from 'react'

import type { VideoTemplateDraft } from '@/features/video/core/contracts/videoTemplateDraft'
import type { ParticlesDraftSlice } from '@/features/video/workspace/templateDraftDomains'

type UseParticlesEditorOptions = {
  templateDraft: VideoTemplateDraft | null
  setTemplateDraft: (draft: VideoTemplateDraft) => void
}

export function useParticlesEditor({
  templateDraft,
  setTemplateDraft,
}: UseParticlesEditorOptions) {
  const patchParticlesDraft = useCallback(
    (patch: Partial<ParticlesDraftSlice>) => {
      if (!templateDraft) {
        return
      }
      const next: VideoTemplateDraft = { ...templateDraft, ...patch }
      setTemplateDraft(next)
    },
    [setTemplateDraft, templateDraft],
  )

  return {
    patchParticlesDraft,
  }
}
