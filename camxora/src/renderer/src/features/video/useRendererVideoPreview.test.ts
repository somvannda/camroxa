import { describe, expect, it, vi } from 'vitest'

import { resolvePreviewImageAssetSource } from '@/features/video/useRendererVideoPreview'

const mockReadFileAsBase64 = vi.fn()

vi.mock('@/shared/api/desktop', () => ({
  getDesktopApi: () => ({
    files: {
      readFileAsBase64: (...args: unknown[]) => mockReadFileAsBase64(...args),
    },
  }),
}))

describe('resolvePreviewImageAssetSource', () => {
  beforeEach(() => {
    mockReadFileAsBase64.mockReset()
  })

  it('returns cached data URLs for local preview assets when desktop decoding is available', async () => {
    mockReadFileAsBase64.mockResolvedValue('abc123')

    await expect(resolvePreviewImageAssetSource('C:\\media\\background image.png')).resolves.toBe(
      'data:image/png;base64,abc123',
    )
    await expect(resolvePreviewImageAssetSource('C:\\media\\background image.png')).resolves.toBe(
      'data:image/png;base64,abc123',
    )

    expect(mockReadFileAsBase64).toHaveBeenCalledTimes(1)
  })

  it('falls back to file URLs for local assets when desktop decoding is unavailable', async () => {
    mockReadFileAsBase64.mockRejectedValue(new Error('missing'))

    await expect(resolvePreviewImageAssetSource('C:\\media\\fallback image.png')).resolves.toBe(
      'file:///C:/media/fallback%20image.png',
    )
  })

  it('preserves pre-resolved remote and blob/data asset sources', async () => {
    await expect(resolvePreviewImageAssetSource('https://example.com/background.png')).resolves.toBe(
      'https://example.com/background.png',
    )
    await expect(resolvePreviewImageAssetSource('blob:http://localhost/logo')).resolves.toBe(
      'blob:http://localhost/logo',
    )
    await expect(resolvePreviewImageAssetSource('data:image/png;base64,abc')).resolves.toBe(
      'data:image/png;base64,abc',
    )
  })
})
