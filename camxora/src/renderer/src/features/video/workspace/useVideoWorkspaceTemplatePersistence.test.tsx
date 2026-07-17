import { act, renderHook } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { buildVideoTemplateDraft } from '@/features/video/core/contracts/videoTemplateDraft'
import { useVideoWorkspaceTemplatePersistence } from '@/features/video/workspace/useVideoWorkspaceTemplatePersistence'

describe('useVideoWorkspaceTemplatePersistence', () => {
  it('builds the final save patch from the local video workspace draft', async () => {
    const patchTemplate = vi.fn().mockResolvedValue(undefined)
    const currentTemplate = {
      style: 'straight-bars',
      layers: [{ id: 'layer-1' }],
      textOverlays: [],
    }
    const templateDraft = {
      ...buildVideoTemplateDraft(currentTemplate, { logoPath: 'D:/logo.png' }),
      style: 'wave-ribbon',
    }

    const { result } = renderHook(() =>
      useVideoWorkspaceTemplatePersistence({
        currentTemplate,
        draftDirtyState: {
          spectrum: true,
          background: false,
          logo: false,
          particles: false,
          text: false,
        },
        editableSpectrumLayers: [{ id: 'layer-2' }],
        patchTemplate,
        templateDraft,
        templateNameDirty: false,
        templateNameDraft: 'Boss Template',
      }),
    )

    expect(result.current.workspaceDirty).toBe(true)

    await act(async () => {
      await result.current.saveWorkspaceTemplate()
    })

    expect(patchTemplate).toHaveBeenCalledWith({
      patch: expect.objectContaining({
        templateName: 'Boss Template',
        style: 'wave-ribbon',
        layers: [{ id: 'layer-2' }],
      }),
      message: 'Saved the current local workspace draft into the selected template.',
    })
  })
})
