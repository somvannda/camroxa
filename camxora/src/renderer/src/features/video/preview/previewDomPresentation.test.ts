import { applyPreviewDomPresentation } from '@/features/video/preview/previewDomPresentation'

const mockResolveBackgroundPresentationState = vi.fn()
const mockResolveLogoPresentationState = vi.fn()

vi.mock('@/features/video/domains/background/backgroundPreviewRuntime', () => ({
  resolveBackgroundPresentationState: (...args: unknown[]) => mockResolveBackgroundPresentationState(...args),
}))

vi.mock('@/features/video/domains/logo/logoPreviewRuntime', () => ({
  resolveLogoPresentationState: (...args: unknown[]) => mockResolveLogoPresentationState(...args),
}))

describe('applyPreviewDomPresentation', () => {
  beforeEach(() => {
    mockResolveBackgroundPresentationState.mockReset()
    mockResolveLogoPresentationState.mockReset()
  })

  it('applies DOM background and logo presentation when both DOM layers are active', () => {
    const backgroundPresentation = { kind: 'background' }
    const logoPresentation = { kind: 'logo' }
    mockResolveBackgroundPresentationState.mockReturnValue(backgroundPresentation)
    mockResolveLogoPresentationState.mockReturnValue(logoPresentation)

    const applyDomBackgroundPresentation = vi.fn()
    const applyDomLogoPresentation = vi.fn()

    applyPreviewDomPresentation({
      applyDomBackgroundPresentation,
      applyDomLogoPresentation,
      backgroundImageRef: { current: null },
      bounds: { width: 1280, height: 720 },
      domBackgroundImageRef: { current: {} as HTMLImageElement },
      domLogoLayerRef: { current: {} as HTMLDivElement },
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
      scale: 1,
      showDomPreviewBackground: true,
      showDomPreviewLogo: true,
      presentationDraft: {} as never,
      timeSec: 1,
    })

    expect(applyDomBackgroundPresentation).toHaveBeenCalledWith(
      expect.anything(),
      backgroundPresentation,
    )
    expect(applyDomLogoPresentation).toHaveBeenCalledWith(
      expect.anything(),
      logoPresentation,
    )
  })

  it('skips DOM application when the relevant DOM layers are inactive', () => {
    const applyDomBackgroundPresentation = vi.fn()
    const applyDomLogoPresentation = vi.fn()

    applyPreviewDomPresentation({
      applyDomBackgroundPresentation,
      applyDomLogoPresentation,
      backgroundImageRef: { current: null },
      bounds: { width: 1280, height: 720 },
      domBackgroundImageRef: { current: null },
      domLogoLayerRef: { current: null },
      motionState: {
        backgroundEnergy: 0,
        backgroundBeatBaseline: 0,
        backgroundPulseDrive: 0.1,
        logoEnergy: 0,
        logoBeatBaseline: 0,
        logoPulseDrive: 0.2,
        flyingGlowLastTriggerDrive: 0,
        flyingGlowPulseDrive: 0,
        flyingGlowLastTriggerSec: -1,
        flyingGlowBeatIntervalSec: 0.2,
      },
      scale: 1,
      showDomPreviewBackground: false,
      showDomPreviewLogo: false,
      presentationDraft: {} as never,
      timeSec: 0,
    })

    expect(mockResolveBackgroundPresentationState).not.toHaveBeenCalled()
    expect(mockResolveLogoPresentationState).not.toHaveBeenCalled()
    expect(applyDomBackgroundPresentation).not.toHaveBeenCalled()
    expect(applyDomLogoPresentation).not.toHaveBeenCalled()
  })
})
