import { render, screen, waitFor } from '@testing-library/react'

import {
  buildSeparatedSpectrumSourceValues,
  RendererVideoPreview,
  resolveBackgroundPresentationState,
  resolveBackgroundReactiveDriveEnergy,
  resolveLogoReactiveDriveEnergy,
  resolveLogoPresentationState,
  type SpectrumReactiveEnvelope,
} from '@/features/video/RendererVideoPreview'
import { buildVideoTemplateDraft } from '@/features/video/core/contracts/videoTemplateDraft'
import {
  smoothPreviewReactiveValue,
  updateFlyingGlowWingEnvelope,
} from '@/features/video/domains/spectrum/spectrumPreviewRuntime'

vi.mock('@/features/video/useRendererVideoPreview', () => ({
  useRendererVideoPreview: () => ({
    backgroundSrc: 'blob:background-preview',
    logoSrc: 'blob:logo-preview',
    capability: 'unsupported',
  }),
}))

class MockImage {
  onload: null | (() => void) = null
  onerror: null | (() => void) = null
  decoding = 'async'
  crossOrigin: string | null = null
  naturalWidth = 1200
  naturalHeight = 1200
  width = 1200
  height = 1200
  complete = false
  private internalSrc = ''

  set src(value: string) {
    this.internalSrc = value
    this.complete = true
    this.onload?.()
  }

  get src(): string {
    return this.internalSrc
  }

  decode(): Promise<void> {
    return Promise.resolve()
  }
}

describe('RendererVideoPreview asset shell layers', () => {
  beforeEach(() => {
    vi.stubGlobal('ResizeObserver', class {
      observe() {}
      disconnect() {}
    })
    vi.stubGlobal('requestAnimationFrame', vi.fn(() => 1))
    vi.stubGlobal('cancelAnimationFrame', vi.fn())
    vi.stubGlobal('Image', MockImage)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders DOM preview layers for ready background and logo assets', async () => {
    const templateDraft = buildVideoTemplateDraft(
      {},
      {
        logoPath: 'C:/assets/logo.png',
      },
    )

    render(
      <RendererVideoPreview
        backgroundPath="C:/assets/background.png"
        logoPath="C:/assets/logo.png"
        playbackCommand={null}
        previewVolume={1}
        selectedMp3Path=""
        selectedTextOverlayIndex={-1}
        template={{}}
        templateDraft={{
          ...templateDraft,
          logoEnabled: true,
        }}
        workspace={{
          playback: {
            isPlaying: false,
            isReady: false,
            isLoading: false,
            currentTimeSec: 0,
            durationSec: 0,
          },
          previewAspectRatio: {
            width: 16,
            height: 9,
          },
        }}
      />,
    )

    await waitFor(() => {
      expect(screen.getByTestId('renderer-dom-background-layer')).toBeInTheDocument()
      expect(screen.getByTestId('renderer-dom-logo-layer')).toBeInTheDocument()
    })
  })
})

describe('RendererVideoPreview background/logo presentation helpers', () => {
  it('uses higher smoothness to slow reactive motion changes', () => {
    const fast = smoothPreviewReactiveValue(0, 1, 1 / 60, 0.1)
    const slow = smoothPreviewReactiveValue(0, 1, 1 / 60, 0.95)

    expect(fast).toBeGreaterThan(slow)
    expect(slow).toBeGreaterThan(0)
  })

  it('makes flying glow wing decay faster when recent beat spacing is faster', () => {
    const fastTempo = updateFlyingGlowWingEnvelope(1, 0, 0, 0, 1, 1 / 60, 0.8, 0.09, 1, 0.45)
    const slowTempo = updateFlyingGlowWingEnvelope(1, 0, 0, 0, 1, 1 / 60, 0.8, 0.32, 1, 0.45)

    expect(fastTempo.pulseDrive).toBeLessThan(slowTempo.pulseDrive)
  })

  it('lets higher flying glow wing release keep the wing open longer after the same beat', () => {
    const fastRelease = updateFlyingGlowWingEnvelope(1, 0, 0, 0, 1, 1 / 60, 0.8, 0.22, 1, 0.1)
    const slowRelease = updateFlyingGlowWingEnvelope(1, 0, 0, 0, 1, 1 / 60, 0.8, 0.22, 1, 2)

    expect(slowRelease.pulseDrive).toBeGreaterThan(fastRelease.pulseDrive + 0.08)
  })

  it('lets flying glow release decay toward a bass-supported floor instead of collapsing straight to zero', () => {
    const noSupport = updateFlyingGlowWingEnvelope(0.28, 0, 0, 0, 1, 1 / 60, 0.82, 0.22, 1, 1)
    const bassSupport = updateFlyingGlowWingEnvelope(0.28, 0.36, 0, 0, 1, 1 / 60, 0.82, 0.22, 1, 1)

    expect(bassSupport.pulseDrive).toBeGreaterThan(noSupport.pulseDrive + 0.002)
  })

  it('smooths flying glow beat-interval updates so one short retrigger does not force an excessively tiny release interval', () => {
    const state = updateFlyingGlowWingEnvelope(0.2, 0.84, 0.84, 0.1, 1, 1 / 60, 0.7, 0.24, 1, 1)

    expect(state.beatIntervalSec).toBeGreaterThan(0.16)
  })

  it('re-triggers the flying glow wing from a new rising beat after it starts closing', () => {
    const triggered = updateFlyingGlowWingEnvelope(0, 0.72, 0.72, 0.08, 0.5, 1 / 60, -1, 0.2, 1, 0.45)
    const decayedA = updateFlyingGlowWingEnvelope(
      triggered.pulseDrive,
      0.04,
      0.04,
      triggered.lastTriggerDrive,
      0.58,
      1 / 60,
      triggered.lastTriggerSec,
      triggered.beatIntervalSec,
      1,
      0.45,
    )
    const decayed = updateFlyingGlowWingEnvelope(
      decayedA.pulseDrive,
      0.02,
      0.02,
      decayedA.lastTriggerDrive,
      0.76,
      1 / 60,
      decayedA.lastTriggerSec,
      decayedA.beatIntervalSec,
      1,
      0.45,
    )
    const retriggered = updateFlyingGlowWingEnvelope(
      decayed.pulseDrive,
      0.78,
      0.78,
      decayed.lastTriggerDrive,
      0.86,
      1 / 60,
      decayed.lastTriggerSec,
      decayed.beatIntervalSec,
      1,
      0.45,
    )

    expect(decayed.pulseDrive).toBeLessThan(decayedA.pulseDrive)
    expect(retriggered.pulseDrive).toBeGreaterThan(decayed.pulseDrive)
  })

  it('does not let bass-only support reopen flying glow without a real trigger pulse', () => {
    const supported = updateFlyingGlowWingEnvelope(0.32, 0.46, 0.08, 0.72, 1, 1 / 60, 0.86, 0.22, 1, 1)

    expect(supported.lastTriggerSec).toBe(0.86)
    expect(supported.pulseDrive).toBeLessThan(0.4)
  })

  it('blocks a fast repeated flying glow trigger while the wing is still visually too open', () => {
    const repeated = updateFlyingGlowWingEnvelope(0.42, 0.18, 0.86, 0.12, 1, 1 / 60, 0.86, 0.22, 1, 1)

    expect(repeated.lastTriggerSec).toBe(0.86)
    expect(repeated.pulseDrive).toBeLessThan(0.5)
  })

  it('allows flying glow to reopen again after the wing has fallen far enough', () => {
    const reopened = updateFlyingGlowWingEnvelope(0.08, 0.18, 0.86, 0.12, 1, 1 / 60, 0.86, 0.22, 1, 1)

    expect(reopened.lastTriggerSec).toBe(1)
    expect(reopened.pulseDrive).toBeGreaterThan(0.12)
  })

  it('lets higher flying glow wing speed open and close the wing faster', () => {
    const slow = updateFlyingGlowWingEnvelope(1, 0, 0, 0, 1, 1 / 60, 0.8, 0.22, 0.5, 1)
    const fast = updateFlyingGlowWingEnvelope(1, 0, 0, 0, 1, 1 / 60, 0.8, 0.22, 8, 1)

    expect(fast.pulseDrive).toBeLessThan(slow.pulseDrive)
  })

  it('does not let support alone keep the flying glow wing hanging too far open', () => {
    const closing = updateFlyingGlowWingEnvelope(0.86, 0.62, 0.02, 0.78, 1, 1 / 60, 0.9, 0.22, 2.4, 1)

    expect(closing.pulseDrive).toBeLessThan(0.8)
  })

  it('builds background motion state that includes reactive zoom and vibrate translation', () => {
    const draft = buildVideoTemplateDraft({}, { logoPath: '' })
    const presentation = resolveBackgroundPresentationState(
      {
        ...draft,
        backgroundMotionMode: 'vibrate',
        backgroundMotionVibrateStrength: 1.4,
        backgroundReactivity: 1.8,
      },
      1280,
      720,
      1920,
      1080,
      0.85,
      0.35,
    )

    expect(presentation.scale).toBe(draft.backgroundUserScale)
    expect(Math.abs(presentation.translateX) + Math.abs(presentation.translateY)).toBeGreaterThan(0.1)
  })

  it('keeps zoom mode at the base scale when there is no audio and pulses larger only on audio', () => {
    const draft = buildVideoTemplateDraft({}, { logoPath: '' })
    const idleZoom = resolveBackgroundPresentationState(
      {
        ...draft,
        backgroundMotionMode: 'zoom',
        backgroundMotionZoomStrength: 20,
        backgroundReactivity: 20,
      },
      1280,
      720,
      1920,
      1080,
      0,
      0.35,
    )
    const activeZoom = resolveBackgroundPresentationState(
      {
        ...draft,
        backgroundMotionMode: 'zoom',
        backgroundMotionZoomStrength: 20,
        backgroundReactivity: 20,
      },
      1280,
      720,
      1920,
      1080,
      0.9,
      0.35,
    )

    expect(idleZoom.scale).toBe(draft.backgroundUserScale)
    expect(activeZoom.scale).toBeGreaterThan(idleZoom.scale)
  })

  it('supports much stronger background motion when the new high-range dials are pushed', () => {
    const draft = buildVideoTemplateDraft({}, { logoPath: '' })
    const lowMotion = resolveBackgroundPresentationState(
      {
        ...draft,
        backgroundMotionMode: 'zoom',
        backgroundMotionZoomStrength: 2,
        backgroundReactivity: 2,
      },
      1280,
      720,
      1920,
      1080,
      0.9,
      0.35,
    )
    const highZoom = resolveBackgroundPresentationState(
      {
        ...draft,
        backgroundMotionMode: 'zoom',
        backgroundMotionZoomStrength: 20,
        backgroundReactivity: 20,
      },
      1280,
      720,
      1920,
      1080,
      0.9,
      0.35,
    )
    const highVibrate = resolveBackgroundPresentationState(
      {
        ...draft,
        backgroundMotionMode: 'vibrate',
        backgroundMotionVibrateStrength: 20,
        backgroundReactivity: 20,
      },
      1280,
      720,
      1920,
      1080,
      0.9,
      0.35,
    )

    expect(highZoom.scale).toBeGreaterThan(lowMotion.scale * 1.4)
    expect(Math.abs(highVibrate.translateX) + Math.abs(highVibrate.translateY)).toBeGreaterThan(20)
  })

  it('makes background audio reactivity increase beat-driven zoom strength without changing idle scale', () => {
    const draft = buildVideoTemplateDraft({}, { logoPath: '' })
    const lowReactivityIdle = resolveBackgroundPresentationState(
      {
        ...draft,
        backgroundMotionMode: 'zoom',
        backgroundMotionZoomStrength: 8,
        backgroundReactivity: 2,
      },
      1280,
      720,
      1920,
      1080,
      0,
      0.35,
    )
    const highReactivityIdle = resolveBackgroundPresentationState(
      {
        ...draft,
        backgroundMotionMode: 'zoom',
        backgroundMotionZoomStrength: 8,
        backgroundReactivity: 16,
      },
      1280,
      720,
      1920,
      1080,
      0,
      0.35,
    )
    const lowReactivityActive = resolveBackgroundPresentationState(
      {
        ...draft,
        backgroundMotionMode: 'zoom',
        backgroundMotionZoomStrength: 8,
        backgroundReactivity: 2,
      },
      1280,
      720,
      1920,
      1080,
      0.42,
      0.35,
    )
    const highReactivityActive = resolveBackgroundPresentationState(
      {
        ...draft,
        backgroundMotionMode: 'zoom',
        backgroundMotionZoomStrength: 8,
        backgroundReactivity: 16,
      },
      1280,
      720,
      1920,
      1080,
      0.42,
      0.35,
    )

    expect(lowReactivityIdle.scale).toBe(highReactivityIdle.scale)
    expect(highReactivityActive.scale).toBeGreaterThan(lowReactivityActive.scale)
  })

  it('keeps logo audio reactivity limited to a clean scale pulse while styling stays stable', () => {
    const draft = buildVideoTemplateDraft({}, { logoPath: '' })
    const rest = resolveLogoPresentationState(
      {
        ...draft,
        logoEnabled: true,
        logoSpinEnabled: true,
        logoSpinSpeed: 180,
        logoReactivity: 1.6,
      },
      960,
      540,
      1,
      0,
      1,
    )
    const reactive = resolveLogoPresentationState(
      {
        ...draft,
        logoEnabled: true,
        logoSpinEnabled: true,
        logoSpinSpeed: 180,
        logoReactivity: 1.6,
      },
      960,
      540,
      1,
      0.9,
      1,
    )

    expect(reactive.size).toBeGreaterThan(rest.size)
    expect(reactive.size).toBeGreaterThan(rest.size * 1.16)
    expect(reactive.glowAlpha).toBe(rest.glowAlpha)
    expect(reactive.outlineAlpha).toBe(rest.outlineAlpha)
    expect(reactive.shadowBlurPx).toBe(rest.shadowBlurPx)
    expect(reactive.shadowOffsetYPx).toBe(rest.shadowOffsetYPx)
    expect(Math.abs(reactive.rotationDeg)).toBeGreaterThan(0)
  })

  it('treats logo audio reactivity as sensitivity instead of direct pulse size growth', () => {
    const draft = buildVideoTemplateDraft({}, { logoPath: '' })
    const lowReactivityIdle = resolveLogoPresentationState(
      {
        ...draft,
        logoEnabled: true,
        logoReactivity: 0.2,
      },
      960,
      540,
      1,
      0,
      1,
    )
    const highReactivityIdle = resolveLogoPresentationState(
      {
        ...draft,
        logoEnabled: true,
        logoReactivity: 2,
      },
      960,
      540,
      1,
      0,
      1,
    )
    const lowReactivityActive = resolveLogoPresentationState(
      {
        ...draft,
        logoEnabled: true,
        logoReactivity: 0.2,
      },
      960,
      540,
      1,
      0.42,
      1,
    )
    const highReactivityActive = resolveLogoPresentationState(
      {
        ...draft,
        logoEnabled: true,
        logoReactivity: 2,
      },
      960,
      540,
      1,
      0.42,
      1,
    )

    expect(lowReactivityIdle.size).toBe(highReactivityIdle.size)
    expect(highReactivityActive.size).toBeGreaterThan(lowReactivityActive.size)
    expect(highReactivityActive.size - lowReactivityActive.size).toBeGreaterThan(draft.logoSizeStep * 100 * 0.02)
    expect(highReactivityActive.size).toBeGreaterThan(highReactivityIdle.size)
  })

  it('changes logo size across real-world logo energy values instead of pinning to one max size', () => {
    const draft = buildVideoTemplateDraft({}, { logoPath: '' })
    const lowerEnergy = resolveLogoPresentationState(
      {
        ...draft,
        logoEnabled: true,
        logoReactivity: 1.95,
      },
      960,
      540,
      1,
      0.65,
      1,
    )
    const higherEnergy = resolveLogoPresentationState(
      {
        ...draft,
        logoEnabled: true,
        logoReactivity: 1.95,
      },
      960,
      540,
      1,
      0.74,
      1,
    )

    expect(higherEnergy.size).toBeGreaterThan(lowerEnergy.size)
  })

  it('builds a more beat-oriented logo drive from kick and drop instead of only sustained energy', () => {
    const sustainOnly = resolveLogoReactiveDriveEnergy(0.82, 0.001, 0.005, 0.005)
    const beatDriven = resolveLogoReactiveDriveEnergy(0.42, 0.03, 0.12, 0.09)

    expect(beatDriven).toBeGreaterThan(sustainOnly)
    expect(sustainOnly).toBeLessThan(0.25)
  })

  it('builds a more beat-oriented background drive instead of relying on sustained loudness only', () => {
    const sustainOnly = resolveBackgroundReactiveDriveEnergy(0.86, 0.001, 0.005, 0.005)
    const beatDriven = resolveBackgroundReactiveDriveEnergy(0.48, 0.12, 0.2, 0.18)

    expect(beatDriven).toBeGreaterThan(sustainOnly)
    expect(sustainOnly).toBeLessThan(0.2)
  })
})

describe('RendererVideoPreview shared spectrum separation', () => {
  it('keeps local spikes alive for non-straight styles instead of flattening the ring into one bed', () => {
    const adjustedValues = new Float32Array(64).fill(0.34)
    adjustedValues[18] = 1.25
    adjustedValues[19] = 0.52

    const envelope: SpectrumReactiveEnvelope = {
      bassFast: 0,
      bassSlow: 0,
      kick: 0,
      drop: 0,
      level: 0,
      bins: null,
      floorBins: null,
      styleKey: '',
    }

    const { sourceValues } = buildSeparatedSpectrumSourceValues(adjustedValues, 1 / 60, envelope, 'orbital-bars', 1)

    expect(sourceValues[18]).toBeGreaterThan(sourceValues[17] * 2)
    expect(sourceValues[18]).toBeGreaterThan(sourceValues[20] * 2)
    expect(sourceValues[17]).toBeLessThan(0.2)
    expect(envelope.styleKey).toBe('orbital-bars')
  })
})
