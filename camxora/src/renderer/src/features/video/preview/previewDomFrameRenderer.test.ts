import { renderPreviewDomFrame } from '@/features/video/preview/previewDomFrameRenderer'

const mockApplyPreviewDomPresentation = vi.fn()
const mockRenderPreviewCanvasComposition = vi.fn()

vi.mock('@/features/video/preview/previewDomPresentation', () => ({
  applyPreviewDomPresentation: (...args: unknown[]) => mockApplyPreviewDomPresentation(...args),
}))

vi.mock('@/features/video/preview/previewCanvasCompositor', () => ({
  renderPreviewCanvasComposition: (...args: unknown[]) => mockRenderPreviewCanvasComposition(...args),
}))

describe('renderPreviewDomFrame', () => {
  beforeEach(() => {
    mockApplyPreviewDomPresentation.mockReset()
    mockRenderPreviewCanvasComposition.mockReset()
  })

  it('delegates DOM presentation and canvas composition through the new seams', () => {
    mockRenderPreviewCanvasComposition.mockReturnValue({
      backdropSource: { kind: 'backdrop' },
      overlaySource: { kind: 'overlay' },
    })
    const drawBackgroundLayer = vi.fn()
    const drawLogoLayer = vi.fn()
    const drawTextOverlays = vi.fn()

    const options = {
      activeTextOverlays: [],
      applyDomBackgroundPresentation: vi.fn(),
      applyDomLogoPresentation: vi.fn(),
      backdropCanvasRef: { current: null },
      backgroundImageRef: { current: null },
      bounds: { width: 1280, height: 720 },
      domBackgroundImageRef: { current: {} as HTMLImageElement },
      domLogoLayerRef: { current: {} as HTMLDivElement },
      dpr: 1,
      drawBackgroundLayer,
      drawLogoLayer,
      drawTextOverlays,
      logicalHeight: 720,
      logicalWidth: 1280,
      logoImageRef: { current: null },
      motionState: {
        backgroundEnergy: 0,
        backgroundBeatBaseline: 0,
        backgroundPulseDrive: 0.3,
        logoEnergy: 0,
        logoBeatBaseline: 0,
        logoPulseDrive: 0.5,
        flyingGlowLastTriggerDrive: 0,
        flyingGlowPulseDrive: 0,
        flyingGlowLastTriggerSec: -1,
        flyingGlowBeatIntervalSec: 0.2,
      },
      overlayCanvasRef: { current: null },
      scale: 1,
      showDomPreviewBackground: true,
      showDomPreviewLogo: true,
      presentationDraft: {} as never,
      timeSec: 1,
    } as const

    const result = renderPreviewDomFrame(options)

    expect(mockApplyPreviewDomPresentation).toHaveBeenCalledWith(
      expect.objectContaining({
        bounds: { width: 1280, height: 720 },
        showDomPreviewBackground: true,
        showDomPreviewLogo: true,
      }),
    )
    expect(mockRenderPreviewCanvasComposition).toHaveBeenCalledWith(
      expect.objectContaining({
        logicalWidth: 1280,
        logicalHeight: 720,
        showDomPreviewBackground: true,
        showDomPreviewLogo: true,
      }),
    )
    expect(result).toEqual(
      expect.objectContaining({
        backdropSource: { kind: 'backdrop' },
        overlaySource: { kind: 'overlay' },
      }),
    )
  })
})
