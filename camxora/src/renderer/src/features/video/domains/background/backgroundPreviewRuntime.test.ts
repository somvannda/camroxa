import {
  resolveBackgroundPresentationState,
  resolveBackgroundReactiveDriveEnergy,
} from '@/features/video/domains/background/backgroundPreviewRuntime'

describe('backgroundPreviewRuntime', () => {
  it('keeps zoom pulse transient so residual reactive energy falls back toward the base scale', () => {
    const draft = {
      backgroundFitMode: 'cover',
      backgroundUserScale: 1,
      backgroundBrightness: 1,
      backgroundReactivity: 20,
      backgroundMotionMode: 'zoom',
      backgroundMotionZoomStrength: 14,
      backgroundMotionVibrateStrength: 0,
      backgroundMotionSpeed: 0,
    } as never

    const kicked = resolveBackgroundPresentationState(draft, 1280, 720, 1920, 1080, 0.9, 1)
    const residual = resolveBackgroundPresentationState(draft, 1280, 720, 1920, 1080, 0, 1.1)

    expect(kicked.scale).toBeGreaterThan(1.2)
    expect(residual.scale).toBeLessThan(kicked.scale)
    expect(residual.scale).toBeLessThan(1.06)
  })

  it('keeps sustain support small so beat pulses do not stay zoomed after the transient passes', () => {
    expect(resolveBackgroundReactiveDriveEnergy(0.9, 0, 0, 0)).toBeCloseTo(0.027, 5)
    expect(resolveBackgroundReactiveDriveEnergy(0.2, 0.18, 0.05, 0.02)).toBeGreaterThan(0.7)
  })

  it('responds earlier on medium pulses so background motion feels more immediate', () => {
    const draft = {
      backgroundFitMode: 'cover',
      backgroundUserScale: 1,
      backgroundBrightness: 1,
      backgroundReactivity: 16,
      backgroundMotionMode: 'zoom',
      backgroundMotionZoomStrength: 10,
      backgroundMotionVibrateStrength: 0,
      backgroundMotionSpeed: 0,
    } as never

    const mediumBeat = resolveBackgroundPresentationState(draft, 1280, 720, 1920, 1080, 0.32, 1)
    expect(mediumBeat.scale).toBeGreaterThan(1.22)
  })

  it('still produces visible motion for lower rhythmic energy so the background does not look dead', () => {
    const draft = {
      backgroundFitMode: 'cover',
      backgroundUserScale: 1,
      backgroundBrightness: 1,
      backgroundReactivity: 12,
      backgroundMotionMode: 'zoom',
      backgroundMotionZoomStrength: 10,
      backgroundMotionVibrateStrength: 0,
      backgroundMotionSpeed: 0,
    } as never

    const lowBedBeat = resolveBackgroundPresentationState(draft, 1280, 720, 1920, 1080, 0.14, 1)
    expect(lowBedBeat.scale).toBeGreaterThan(1.08)
  })

  it('lets zoom react on moderate pulses more like vibrate does', () => {
    const draft = {
      backgroundFitMode: 'cover',
      backgroundUserScale: 1,
      backgroundBrightness: 1,
      backgroundReactivity: 12,
      backgroundMotionMode: 'zoom',
      backgroundMotionZoomStrength: 8,
      backgroundMotionVibrateStrength: 0,
      backgroundMotionSpeed: 0,
    } as never

    const moderatePulse = resolveBackgroundPresentationState(draft, 1280, 720, 1920, 1080, 0.18, 1)
    expect(moderatePulse.scale).toBeGreaterThan(1.16)
  })
})
