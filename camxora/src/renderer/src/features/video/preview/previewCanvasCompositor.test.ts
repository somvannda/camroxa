import { renderPreviewCanvasComposition } from '@/features/video/preview/previewCanvasCompositor'

const mockResolveBackgroundPresentationState = vi.fn()
const mockResolveLogoPresentationState = vi.fn()

vi.mock('@/features/video/domains/background/backgroundPreviewRuntime', () => ({
  resolveBackgroundPresentationState: (...args: unknown[]) => mockResolveBackgroundPresentationState(...args),
}))

vi.mock('@/features/video/domains/logo/logoPreviewRuntime', () => ({
  resolveLogoPresentationState: (...args: unknown[]) => mockResolveLogoPresentationState(...args),
}))

function createCanvasMock() {
  const context = {
    clearRect: vi.fn(),
    setTransform: vi.fn(),
  }
  return {
    canvas: {
      width: 0,
      height: 0,
      getContext: vi.fn().mockReturnValue(context),
    } as unknown as HTMLCanvasElement,
    context,
  }
}

describe('renderPreviewCanvasComposition', () => {
  beforeEach(() => {
    mockResolveBackgroundPresentationState.mockReset()
    mockResolveLogoPresentationState.mockReset()
  })

  it('renders backdrop, logo, and text into canvas sources when DOM layers are inactive', () => {
    const backgroundPresentation = { kind: 'background' }
    const logoPresentation = { kind: 'logo' }
    mockResolveBackgroundPresentationState.mockReturnValue(backgroundPresentation)
    mockResolveLogoPresentationState.mockReturnValue(logoPresentation)

    const backdrop = createCanvasMock()
    const overlay = createCanvasMock()
    const drawBackgroundLayer = vi.fn()
    const drawLogoLayer = vi.fn()
    const drawTextOverlays = vi.fn()

    const result = renderPreviewCanvasComposition({
      activeTextOverlays: [{ key: 'title' }],
      backdropCanvasRef: { current: backdrop.canvas },
      backgroundImageRef: { current: null },
      dpr: 2,
      drawBackgroundLayer,
      drawLogoLayer,
      drawTextOverlays,
      logicalHeight: 360,
      logicalWidth: 640,
      logoImageRef: { current: null },
      motionState: {
        backgroundEnergy: 0,
        backgroundBeatBaseline: 0,
        backgroundPulseDrive: 0.2,
        logoEnergy: 0,
        logoBeatBaseline: 0,
        logoPulseDrive: 0.4,
        flyingGlowLastTriggerDrive: 0,
        flyingGlowPulseDrive: 0,
        flyingGlowLastTriggerSec: -1,
        flyingGlowBeatIntervalSec: 0.2,
      },
      overlayCanvasRef: { current: overlay.canvas },
      scale: 1,
      showDomPreviewBackground: false,
      showDomPreviewLogo: false,
      presentationDraft: {} as never,
      timeSec: 2,
    })

    expect(backdrop.canvas.width).toBe(1280)
    expect(backdrop.canvas.height).toBe(720)
    expect(overlay.canvas.width).toBe(1280)
    expect(overlay.canvas.height).toBe(720)
    expect(drawBackgroundLayer).toHaveBeenCalledWith(
      backdrop.context,
      null,
      1280,
      720,
      backgroundPresentation,
    )
    expect(drawLogoLayer).toHaveBeenCalledWith(
      overlay.context,
      expect.anything(),
      null,
      logoPresentation,
    )
    expect(drawTextOverlays).toHaveBeenCalledWith(
      overlay.context,
      [{ key: 'title' }],
      1280,
      720,
    )
    expect(result).toEqual({
      backdropSource: backdrop.canvas,
      overlaySource: overlay.canvas,
    })
  })

  it('returns no canvas sources when DOM layers stay active and there are no text overlays', () => {
    const drawBackgroundLayer = vi.fn()
    const drawLogoLayer = vi.fn()
    const drawTextOverlays = vi.fn()

    const result = renderPreviewCanvasComposition({
      activeTextOverlays: [],
      backdropCanvasRef: { current: null },
      backgroundImageRef: { current: null },
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
        backgroundPulseDrive: 0.1,
        logoEnergy: 0,
        logoBeatBaseline: 0,
        logoPulseDrive: 0.1,
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
      timeSec: 0,
    })

    expect(drawBackgroundLayer).not.toHaveBeenCalled()
    expect(drawLogoLayer).not.toHaveBeenCalled()
    expect(drawTextOverlays).not.toHaveBeenCalled()
    expect(result).toEqual({
      backdropSource: null,
      overlaySource: null,
    })
  })
})
