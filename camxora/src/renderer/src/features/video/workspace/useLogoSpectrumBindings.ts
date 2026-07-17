import { useCallback } from 'react'

import type { TemplateSettingsDraft } from '@/features/settings/settingsTemplateDraft'
import {
  applyLogoShapeDraftChange,
  applyLogoSizeDraftChange,
  applySpectrumAttachToLogoDraftChange,
} from '@/features/video/core/scene/logoSpectrumBindings'
import type { LogoDraftSlice } from '@/features/video/workspace/templateDraftDomains'

type UseLogoSpectrumBindingsOptions = {
  templateDraft: TemplateSettingsDraft | null
  commitLogoDraft: (next: TemplateSettingsDraft) => void
  commitSpectrumSessionDraft: (next: TemplateSettingsDraft) => void
}

export function useLogoSpectrumBindings({
  templateDraft,
  commitLogoDraft,
  commitSpectrumSessionDraft,
}: UseLogoSpectrumBindingsOptions) {
  const patchLogoDraft = useCallback(
    (patch: Partial<LogoDraftSlice>) => {
      if (!templateDraft) {
        return
      }
      commitLogoDraft({ ...templateDraft, ...patch })
    },
    [commitLogoDraft, templateDraft],
  )

  const applyLogoShape = useCallback(
    (value: string) => {
      if (!templateDraft) {
        return
      }
      const next = applyLogoShapeDraftChange(templateDraft, value)
      commitSpectrumSessionDraft(next)
      commitLogoDraft(next)
    },
    [commitLogoDraft, commitSpectrumSessionDraft, templateDraft],
  )

  const applyLogoSize = useCallback(
    (value: number) => {
      if (!templateDraft) {
        return
      }
      const next = applyLogoSizeDraftChange(templateDraft, value)
      commitLogoDraft(next)
    },
    [commitLogoDraft, templateDraft],
  )

  const setSpectrumLogoGap = useCallback(
    (value: number) => {
      if (!templateDraft) {
        return
      }
      commitSpectrumSessionDraft({ ...templateDraft, spectrumLogoGap: value })
    },
    [commitSpectrumSessionDraft, templateDraft],
  )

  const toggleSpectrumAttachment = useCallback(
    (checked: boolean) => {
      if (!templateDraft) {
        return
      }
      const next = applySpectrumAttachToLogoDraftChange(templateDraft, checked)
      commitSpectrumSessionDraft(next)
    },
    [commitSpectrumSessionDraft, templateDraft],
  )

  return {
    applyLogoShape,
    applyLogoSize,
    patchLogoDraft,
    setSpectrumLogoGap,
    toggleSpectrumAttachment,
  }
}
