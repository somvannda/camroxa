import { buildTemplateDraft } from '@/features/settings/settingsTemplateDraft'
import {
  clearVideoWorkspaceDraftSnapshot,
  readVideoWorkspaceDraftSnapshot,
  writeVideoWorkspaceDraftSnapshot,
} from '@/features/video/workspace/videoWorkspaceDraftStore'

describe('videoWorkspaceDraftStore', () => {
  const storagePrefix = 'test.video.workspace-draft'

  beforeEach(() => {
    window.localStorage.clear()
  })

  it('round-trips a persisted local workspace draft through localStorage', () => {
    const draft = buildTemplateDraft(
      {
        style: 'flying-glow',
        backgroundSettings: { fitMode: 'contain' },
        previewBindings: { spectrumAttachToLogo: true, spectrumLogoGap: 42 },
        textOverlays: [{ text: 'Boss', enabled: true }],
      },
      { logoPath: 'D:/logo.png' },
    )

    writeVideoWorkspaceDraftSnapshot(storagePrefix, 'template-1', {
      draft,
      layers: [{ id: 'layer-1' }, { id: 'layer-2' }],
      templateName: 'Local Workspace',
    })

    expect(
      readVideoWorkspaceDraftSnapshot(storagePrefix, 'template-1', draft, 'Persisted Template'),
    ).toEqual({
      draft,
      layers: [{ id: 'layer-1' }, { id: 'layer-2' }],
      templateName: 'Local Workspace',
    })
  })

  it('supports clearing a stored workspace draft snapshot', () => {
    const draft = buildTemplateDraft({}, { logoPath: '' })
    writeVideoWorkspaceDraftSnapshot(storagePrefix, 'template-2', {
      draft,
      layers: [{ id: 'layer-1' }],
      templateName: 'Workspace Name',
    })

    clearVideoWorkspaceDraftSnapshot(storagePrefix, 'template-2')

    expect(readVideoWorkspaceDraftSnapshot(storagePrefix, 'template-2', draft, 'Persisted')).toBeNull()
  })
})
