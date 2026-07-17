import { describe, expect, it } from 'vitest'

import { buildTemplateDraft } from '@/features/settings/settingsTemplateDraft'
import {
  buildVideoWorkspaceDraftDirtyState,
  buildVideoWorkspaceDraftSlices,
} from '@/features/video/workspace/templateDraftDomains'

describe('templateDraftDomains', () => {
  it('builds explicit workspace draft slices from the aggregate template draft', () => {
    const draft = buildTemplateDraft(
      {
        spectrumEnabled: true,
        style: 'flying-glow',
        audioSettings: {
          inputGain: 1.4,
          barHeight: 1.35,
          bandContrast: 1.25,
          transientFocus: 1.15,
          kickImpact: 0.85,
          bassEmphasis: 1.4,
          trebleShimmer: 1.2,
          peakHoldBlend: 0.35,
          motionSmoothing: 0.52,
          flyingGlowWingMotionSpeed: 1.6,
          flyingGlowWingRelease: 1.1,
        },
        previewBindings: {
          spectrumAttachToLogo: true,
          spectrumLogoGap: 34,
        },
        position: {
          anchor: 'bottom-center',
          x: 12,
          y: -18,
        },
        backgroundSettings: {
          enabled: false,
          fitMode: 'contain',
          userScale: 1.35,
          brightness: 1.1,
          reactivity: 4.2,
          smoothing: 0.62,
          motionMode: 'zoom',
          motionZoomStrength: 8.5,
          motionVibrateStrength: 0.4,
        },
        effects: {
          vignette: {
            enabled: true,
            strength: 0.45,
            feather: 0.55,
            opacity: 0.5,
            color: '#111111',
          },
          smoke: {
            enabled: true,
            strength: 0.35,
            blur: 0.65,
            noise: 0.4,
            speed: 0.25,
            opacity: 0.33,
            color: '#222222',
          },
        },
        logoSettings: {
          enabled: true,
          spinEnabled: true,
          spinDirection: 'ccw',
          spinSpeed: 180,
          circleMask: false,
          size: 340,
          opacity: 0.8,
          reactivity: 0.7,
          smoothing: 0.4,
        },
        particlesSettings: {
          enabled: true,
          maxCount: 900,
          spawnRate: 420,
          lifetimeSec: 2.2,
          speed: 3.4,
          reactivity: 0.2,
          smoothing: 0.55,
          spawnMode: 'burst',
          spawnTrigger: 'beat',
          spawnThreshold: 0.22,
          variant: 'bubble',
          spawnArea: 'fullFrame',
          sizeJitter: 0.3,
          drift: 0.22,
          swirl: 0.18,
          style: 'glow',
          size: 6,
          opacity: 0.48,
          color: '#ffffff',
          reactColor: '#ff00ff',
          reactStrength: 0.8,
        },
        textOverlays: [
          {
            enabled: true,
            text: 'Boss',
            startSec: 1,
            durationSec: 4,
            anchor: 'top-center',
            x: 0,
            y: 32,
            sizePx: 64,
            color: '#ffffff',
            strokeColor: '#000000',
            strokeWidth: 2,
            shadow: 0.45,
            animation: 'fade',
          },
        ],
      },
      { logoPath: 'D:/logos/main.png' },
    )

    const slices = buildVideoWorkspaceDraftSlices(draft)

    expect(slices.spectrum.style).toBe('flying-glow')
    expect(slices.spectrum.spectrumLogoGap).toBe(34)
    expect(slices.spectrum.audioBarHeight).toBe(1.35)
    expect(slices.spectrum.audioBassEmphasis).toBe(1.4)
    expect(slices.spectrum.audioTrebleShimmer).toBe(1.2)
    expect(slices.spectrum.audioPeakHoldBlend).toBe(0.35)
    expect(slices.spectrum.flyingGlowWingMotionSpeed).toBe(1.6)
    expect(slices.background.backgroundEnabled).toBe(false)
    expect(slices.background.backgroundFitMode).toBe('contain')
    expect(slices.background.smokeEnabled).toBe(true)
    expect(slices.logo.logoPath).toBe('D:/logos/main.png')
    expect(slices.logo.logoShape).toBe('square')
    expect(slices.particles.particlesSpawnMode).toBe('burst')
    expect(slices.text.textOverlays).toHaveLength(1)
  })

  it('tracks dirty state per domain without cross-domain bleed', () => {
    const persisted = buildTemplateDraft(
      {
        style: 'straight-bars',
        backgroundSettings: { brightness: 1, fitMode: 'cover' },
        logoSettings: { size: 200, circleMask: true, enabled: true },
        particlesSettings: { speed: 1, enabled: true },
        textOverlays: [],
      },
      { logoPath: 'D:/logo.png' },
    )

    const local = {
      ...persisted,
      backgroundBrightness: 1.35,
    }

    expect(buildVideoWorkspaceDraftDirtyState(local, persisted, { spectrumDirty: false })).toEqual({
      spectrum: false,
      background: true,
      logo: false,
      particles: false,
      text: false,
    })
  })
})
