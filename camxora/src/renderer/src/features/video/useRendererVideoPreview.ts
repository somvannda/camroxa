import { useEffect, useMemo, useState } from 'react'

import { createVideoDebugSender } from '@/features/video/videoDiagnostics'
import { getDesktopApi } from '@/shared/api/desktop'

export type RendererPreviewCapability = 'webgpu' | 'webgl2' | 'webgl' | 'css'

type UseRendererVideoPreviewInput = {
  backgroundPath: string
  logoPath: string
}

type UseRendererVideoPreviewResult = {
  capability: RendererPreviewCapability
  capabilityLabel: string
  message: string
  backgroundSrc: string | null
  logoSrc: string | null
}

const sendVideoPageLagDebug = createVideoDebugSender({
  sessionId: 'video-page-lag',
  runId: 'pre-fix',
})
const previewImageSourceCache = new Map<string, Promise<string | null>>()

export function getPreviewImageMimeType(targetPath: string): string {
  const normalized = targetPath.toLowerCase()
  if (normalized.endsWith('.png')) {
    return 'image/png'
  }
  if (normalized.endsWith('.jpg') || normalized.endsWith('.jpeg')) {
    return 'image/jpeg'
  }
  if (normalized.endsWith('.webp')) {
    return 'image/webp'
  }
  if (normalized.endsWith('.gif')) {
    return 'image/gif'
  }
  if (normalized.endsWith('.svg')) {
    return 'image/svg+xml'
  }
  if (normalized.endsWith('.bmp')) {
    return 'image/bmp'
  }
  if (normalized.endsWith('.avif')) {
    return 'image/avif'
  }
  return 'application/octet-stream'
}

function toFileUrl(targetPath: string): string {
  const normalized = targetPath.trim().replace(/\\/g, '/')
  if (!normalized) {
    return ''
  }
  if (/^[a-z]+:\/\//i.test(normalized)) {
    return normalized
  }
  if (/^[a-z]:\//i.test(normalized)) {
    return encodeURI(`file:///${normalized}`)
  }
  return encodeURI(`file://${normalized.startsWith('/') ? '' : '/'}${normalized}`)
}

function detectRendererCapability(): RendererPreviewCapability {
  if (typeof navigator !== 'undefined' && 'gpu' in navigator) {
    return 'webgpu'
  }
  if (typeof navigator !== 'undefined' && /jsdom/i.test(navigator.userAgent)) {
    return 'css'
  }
  if (typeof document === 'undefined') {
    return 'css'
  }
  const canvas = document.createElement('canvas')
  try {
    if (canvas.getContext('webgl2')) {
      return 'webgl2'
    }
    if (canvas.getContext('webgl')) {
      return 'webgl'
    }
  } catch {
    return 'css'
  }
  return 'css'
}

export async function resolvePreviewImageAssetSource(targetPath: string): Promise<string | null> {
  const normalized = targetPath.trim()
  if (!normalized) {
    return null
  }
  if (/^(https?:\/\/|data:|blob:)/i.test(normalized)) {
    return normalized
  }

  const cached = previewImageSourceCache.get(normalized)
  if (cached) {
    return cached
  }

  const sourcePromise = (async () => {
    try {
      const readStart = performance.now()
      const base64 = await getDesktopApi().files.readFileAsBase64(normalized)
      // #region debug-point A:image-source-base64
      sendVideoPageLagDebug({
        hypothesisId: 'A',
        location: 'useRendererVideoPreview:resolvePreviewImageAssetSource',
        msg: '[DEBUG] preview image source base64 read completed',
        data: {
          targetPath: normalized,
          elapsedMs: Number((performance.now() - readStart).toFixed(2)),
          base64Length: base64?.length ?? 0,
        },
      })
      // #endregion
      if (base64) {
        return `data:${getPreviewImageMimeType(normalized)};base64,${base64}`
      }
    } catch {
      // Fall back to a file URL when desktop decoding is unavailable.
    }

    const fileUrl = toFileUrl(normalized)
    // #region debug-point A:image-source-file-url
    sendVideoPageLagDebug({
      hypothesisId: 'A',
      location: 'useRendererVideoPreview:resolvePreviewImageAssetSource',
      msg: '[DEBUG] preview image source resolved to file URL',
      data: {
        targetPath: normalized,
        mimeType: getPreviewImageMimeType(normalized),
        fileUrlPrefix: fileUrl.slice(0, 48),
      },
    })
    // #endregion
    return fileUrl
  })()

  previewImageSourceCache.set(normalized, sourcePromise)
  return sourcePromise
}

export function useRendererVideoPreview(
  input: UseRendererVideoPreviewInput,
): UseRendererVideoPreviewResult {
  const [backgroundSrc, setBackgroundSrc] = useState<string | null>(null)
  const [logoSrc, setLogoSrc] = useState<string | null>(null)

  const capability = useMemo(() => detectRendererCapability(), [])
  const isJsdom = typeof navigator !== 'undefined' && /jsdom/i.test(navigator.userAgent)

  useEffect(() => {
    if (isJsdom) {
      setBackgroundSrc(input.backgroundPath.trim() ? toFileUrl(input.backgroundPath) : null)
      return
    }
    let cancelled = false

    void resolvePreviewImageAssetSource(input.backgroundPath).then((nextSource) => {
      if (!cancelled) {
        setBackgroundSrc(nextSource)
      }
    })

    return () => {
      cancelled = true
    }
  }, [input.backgroundPath, isJsdom])

  useEffect(() => {
    if (isJsdom) {
      setLogoSrc(input.logoPath.trim() ? toFileUrl(input.logoPath) : null)
      return
    }
    let cancelled = false

    void resolvePreviewImageAssetSource(input.logoPath).then((nextSource) => {
      if (!cancelled) {
        setLogoSrc(nextSource)
      }
    })

    return () => {
      cancelled = true
    }
  }, [input.logoPath, isJsdom])

  const capabilityLabel =
    capability === 'webgpu'
      ? 'WebGPU Ready'
      : capability === 'webgl2'
        ? 'WebGL2 Ready'
        : capability === 'webgl'
          ? 'WebGL Ready'
          : 'CSS Fallback'

  const message =
    capability === 'webgpu'
      ? 'Renderer preview is live in the workspace. WebGPU is available for the next compositor phase.'
      : capability === 'webgl2'
        ? 'Renderer preview is live in the workspace. WebGL2 is available for the next compositor phase.'
        : capability === 'webgl'
          ? 'Renderer preview is live in the workspace. WebGL fallback is available for the next compositor phase.'
          : 'Renderer preview is live in the workspace with a CSS-safe fallback while the GPU compositor is built.'

  return {
    capability,
    capabilityLabel,
    message,
    backgroundSrc,
    logoSrc,
  }
}
