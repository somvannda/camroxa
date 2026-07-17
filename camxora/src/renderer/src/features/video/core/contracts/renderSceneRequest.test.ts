import { buildVideoTemplateDraft } from '@/features/video/core/contracts/videoTemplateDraft'
import {
  buildManualRenderSceneRequest,
  buildPipelineRenderSceneRequest,
  buildVideoRenderOutputSettings,
  computePreviewSceneScale,
  parseRenderResolution,
} from '@/features/video/core/contracts/renderSceneRequest'

describe('renderSceneRequest', () => {
  it('parses normalized output resolution strings', () => {
    expect(parseRenderResolution('2560x1440')).toEqual({ width: 2560, height: 1440 })
    expect(parseRenderResolution('broken')).toEqual({ width: 1920, height: 1080 })
  })

  it('builds manual render requests from the live draft', () => {
    const draft = buildVideoTemplateDraft(
      {
        style: 'flying-glow',
        particles: {
          enabled: true,
          speed: 8.4,
        },
      },
      { logoPath: 'D:/workspace-logo.png' },
    )
    const liveDraft = {
      ...draft,
      particlesSpeed: 12.5,
      backgroundBrightness: 0.42,
      logoPath: 'D:/draft-logo.png',
    }

    const request = buildManualRenderSceneRequest({
      template: { style: 'flying-glow' },
      templateDraft: liveDraft,
      workspace: {
        templateId: 'template-live',
        outputResolution: '3840x2160',
        logoPath: 'D:/workspace-logo.png',
        selectedMp3Path: 'D:/workspace-song.mp3',
      },
      backgroundPath: 'D:/backgrounds/current.png',
      selectedMp3Path: 'D:/exports/manual-song.mp3',
      fps: 30,
    })

    expect(request.mode).toBe('manual')
    expect(request.draft).toBe(liveDraft)
    expect(request.context.draftSource).toBe('live')
    expect(request.assets.backgroundPath).toBe('D:/backgrounds/current.png')
    expect(request.assets.logoPath).toBe('D:/draft-logo.png')
    expect(request.assets.audioPath).toBe('D:/exports/manual-song.mp3')
    expect(request.output).toEqual({
      resolution: '3840x2160',
      width: 3840,
      height: 2160,
      fps: 30,
    })
  })

  it('builds pipeline render requests from saved template state', () => {
    const template = {
      style: 'straight-bars',
      logoSettings: {
        enabled: true,
        size: 180,
      },
      particles: {
        enabled: true,
        speed: 4.5,
      },
    }

    const request = buildPipelineRenderSceneRequest({
      template,
      workspace: {
        templateId: 'template-saved',
        outputResolution: '1920x1080',
        logoPath: 'D:/saved-logo.png',
        selectedMp3Path: 'D:/workspace-default.mp3',
      },
      runDir: 'D:/runs/batch-01',
      backgroundPath: 'D:/runs/batch-01/backgrounds/song-a.png',
      branch: 'long',
      batchId: 'batch-01',
      role: 'primary',
      selectedMp3Path: 'D:/runs/batch-01/song-a.mp3',
    })

    expect(request.mode).toBe('pipeline')
    expect(request.context).toEqual({
      templateId: 'template-saved',
      branch: 'long',
      batchId: 'batch-01',
      role: 'primary',
      draftSource: 'saved',
    })
    expect(request.assets).toEqual({
      backgroundPath: 'D:/runs/batch-01/backgrounds/song-a.png',
      logoPath: 'D:/saved-logo.png',
      audioPath: 'D:/runs/batch-01/song-a.mp3',
      runDir: 'D:/runs/batch-01',
    })
    expect(request.draft.logoPath).toBe('D:/saved-logo.png')
    expect(request.output).toEqual(buildVideoRenderOutputSettings('1920x1080'))
  })

  it('computes preview scale from aspect-only references consistently', () => {
    expect(
      computePreviewSceneScale(
        { width: 960, height: 540 },
        { width: 16, height: 9 },
      ),
    ).toBeCloseTo(0.5, 4)
  })
})
