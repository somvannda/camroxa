import { describe, expect, it } from 'vitest'

import { buildDefaultTextOverlayDraft, buildVideoTemplateDraft } from '@/features/video/core/contracts/videoTemplateDraft'
import { buildVideoWorkspaceTemplateSavePatch } from '@/features/video/workspace/videoWorkspaceTemplateSave'

describe('buildVideoWorkspaceTemplateSavePatch', () => {
  it('assembles the explicit video workspace save payload from the local draft', () => {
    const template = {
      style: 'straight-bars',
      layers: [{ id: 'persisted-layer' }],
      textOverlays: [],
    }
    const draft = {
      ...buildVideoTemplateDraft(template, { logoPath: 'D:/logo.png' }),
      style: 'flying-glow',
      spectrumEnabled: true,
      effectPacks: {
        spectrum: {
          packId: 'spectrum-pack',
          version: '1.2.3',
        },
      },
      textOverlays: [
        {
          ...buildDefaultTextOverlayDraft(),
          text: 'Boss Diagnostics',
        },
      ],
    }
    const layers = [{ id: 'local-layer', gain: 0.8 }]

    const result = buildVideoWorkspaceTemplateSavePatch({
      template,
      draft,
      templateName: ' Boss Template ',
      layers,
    })

    expect(result.templateName).toBe('Boss Template')
    expect(result.style).toBe('flying-glow')
    expect(result.effectPacks).toEqual(
      expect.objectContaining({
        spectrum: {
          packId: 'spectrum-pack',
          version: '1.2.3',
        },
      }),
    )
    expect(result.textOverlays).toEqual([
      expect.objectContaining({
        text: 'Boss Diagnostics',
      }),
    ])
    expect(result.layers).toEqual([{ id: 'local-layer', gain: 0.8 }])
    expect(result.layers).not.toBe(layers)
  })
})
