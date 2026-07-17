import { renderHook } from '@testing-library/react'

import { usePreviewAssetService } from '@/features/video/preview/usePreviewAssetService'

const mockUseRendererVideoPreview = vi.fn()
const mockUsePreviewAssetManager = vi.fn()

vi.mock('@/features/video/useRendererVideoPreview', () => ({
  useRendererVideoPreview: (args: unknown) => mockUseRendererVideoPreview(args),
}))

vi.mock('@/features/video/preview/usePreviewAssetManager', () => ({
  usePreviewAssetManager: (args: unknown) => mockUsePreviewAssetManager(args),
}))

describe('usePreviewAssetService', () => {
  beforeEach(() => {
    mockUseRendererVideoPreview.mockReset()
    mockUsePreviewAssetManager.mockReset()
  })

  it('combines source resolution with asset decode state', () => {
    const backgroundImageRef = { current: null }
    const logoImageRef = { current: null }

    mockUseRendererVideoPreview.mockReturnValue({
      backgroundSrc: 'blob:background',
      capability: 'webgpu',
      logoSrc: 'blob:logo',
    })
    mockUsePreviewAssetManager.mockReturnValue({
      backgroundImageRef,
      backgroundLoadStatus: 'ready',
      logoImageRef,
      logoLoadStatus: 'loading',
      logoVisibleRadiusRatio: 0.82,
    })

    const { result } = renderHook(() =>
      usePreviewAssetService({
        backgroundPath: 'D:/background.png',
        logoEnabled: true,
        logoPath: 'D:/logo.png',
        logoShape: 'circle',
      }),
    )

    expect(mockUseRendererVideoPreview).toHaveBeenCalledWith({
      backgroundPath: 'D:/background.png',
      logoPath: 'D:/logo.png',
    })
    expect(mockUsePreviewAssetManager).toHaveBeenCalledWith({
      backgroundSrc: 'blob:background',
      logoEnabled: true,
      logoShape: 'circle',
      logoSrc: 'blob:logo',
    })
    expect(result.current).toEqual({
      backgroundImageRef,
      backgroundLoadStatus: 'ready',
      backgroundSrc: 'blob:background',
      capability: 'webgpu',
      logoImageRef,
      logoLoadStatus: 'loading',
      logoSrc: 'blob:logo',
      logoVisibleRadiusRatio: 0.82,
    })
  })
})
