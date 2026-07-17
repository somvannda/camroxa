import { useCallback } from 'react'

import type { VideoTemplateDraft } from '@/features/video/core/contracts/videoTemplateDraft'

type DesktopApiLike = {
  files: {
    selectFile: (options: {
      title: string
      filters: Array<{ name: string; extensions: string[] }>
    }) => Promise<string | null>
  }
  video: {
    setLogoPath: (path: string) => Promise<unknown>
  }
}

type UseLogoEditorOptions = {
  templateDraft: VideoTemplateDraft | null
  setTemplateDraft: (draft: VideoTemplateDraft) => void
  desktopApi: DesktopApiLike
  emitStatus: (tone: 'success' | 'error', message: string) => void
}

export function useLogoEditor({
  templateDraft,
  setTemplateDraft,
  desktopApi,
  emitStatus,
}: UseLogoEditorOptions) {
  const commitLogoDraft = useCallback(
    (next: VideoTemplateDraft) => {
      setTemplateDraft(next)
    },
    [setTemplateDraft],
  )

  const selectLogo = useCallback(async () => {
    if (!templateDraft) {
      return
    }
    try {
      const selectedPath = await desktopApi.files.selectFile({
        title: 'Select logo',
        filters: [{ name: 'Images', extensions: ['png', 'jpg', 'jpeg', 'webp'] }],
      })
      if (!selectedPath) {
        return
      }
      await desktopApi.video.setLogoPath(selectedPath)
      commitLogoDraft({ ...templateDraft, logoPath: selectedPath })
    } catch (error) {
      emitStatus('error', error instanceof Error ? error.message : 'Unable to select a logo right now.')
    }
  }, [commitLogoDraft, desktopApi.files, desktopApi.video, emitStatus, templateDraft])

  return {
    commitLogoDraft,
    selectLogo,
  }
}
