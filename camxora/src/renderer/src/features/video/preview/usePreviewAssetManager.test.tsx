import { renderHook, waitFor } from '@testing-library/react'

import { usePreviewAssetManager } from '@/features/video/preview/usePreviewAssetManager'

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

describe('usePreviewAssetManager', () => {
  beforeEach(() => {
    vi.stubGlobal('Image', MockImage)
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(null)
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('loads background and logo assets into ready state', async () => {
    const { result } = renderHook(() =>
      usePreviewAssetManager({
        backgroundSrc: 'blob:background-preview',
        logoEnabled: true,
        logoShape: 'circle',
        logoSrc: 'blob:logo-preview',
      }),
    )

    await waitFor(() => {
      expect(result.current.backgroundLoadStatus).toBe('ready')
      expect(result.current.logoLoadStatus).toBe('ready')
    })

    expect(result.current.backgroundImageRef.current?.src).toBe('blob:background-preview')
    expect(result.current.logoImageRef.current?.src).toBe('blob:logo-preview')
    expect(result.current.logoVisibleRadiusRatio).toBe(1)
  })

  it('falls back to idle states when assets are missing', () => {
    const { result } = renderHook(() =>
      usePreviewAssetManager({
        backgroundSrc: null,
        logoEnabled: false,
        logoShape: 'square',
        logoSrc: null,
      }),
    )

    expect(result.current.backgroundLoadStatus).toBe('idle')
    expect(result.current.logoLoadStatus).toBe('idle')
    expect(result.current.logoVisibleRadiusRatio).toBe(1)
  })
})
