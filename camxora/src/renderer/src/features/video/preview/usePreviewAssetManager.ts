import { useEffect, useRef, useState } from 'react'

import { createVideoDebugSender } from '@/features/video/videoDiagnostics'

export type PreviewAssetLoadStatus = 'idle' | 'loading' | 'ready' | 'error'

type UsePreviewAssetManagerOptions = {
  backgroundSrc: string | null
  logoEnabled: boolean
  logoShape: string
  logoSrc: string | null
}

type UsePreviewAssetManagerResult = {
  backgroundImageRef: React.MutableRefObject<HTMLImageElement | null>
  backgroundLoadStatus: PreviewAssetLoadStatus
  logoImageRef: React.MutableRefObject<HTMLImageElement | null>
  logoLoadStatus: PreviewAssetLoadStatus
  logoVisibleRadiusRatio: number
}

const LOGO_ANALYSIS_SIZE = 256
const sendVideoPageLagDebug = createVideoDebugSender({
  sessionId: 'video-page-lag',
  runId: 'pre-fix',
})

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value))
}

function isRemoteAssetSource(source: string): boolean {
  return /^https?:\/\//i.test(source)
}

async function measureVisibleLogoRadiusRatio(
  logoSrc: string,
  logoShape: string,
): Promise<number> {
  if (typeof window === 'undefined' || typeof document === 'undefined') {
    return 1
  }

  const image = new Image()
  image.decoding = 'async'
  image.crossOrigin = 'anonymous'
  image.src = logoSrc

  await new Promise<void>((resolve, reject) => {
    image.onload = () => resolve()
    image.onerror = () => reject(new Error('Unable to load logo for bounds analysis.'))
  })

  const canvas = document.createElement('canvas')
  canvas.width = LOGO_ANALYSIS_SIZE
  canvas.height = LOGO_ANALYSIS_SIZE
  const context = canvas.getContext('2d', { willReadFrequently: true })
  if (!context) {
    return 1
  }

  const sourceSize = Math.min(image.naturalWidth || LOGO_ANALYSIS_SIZE, image.naturalHeight || LOGO_ANALYSIS_SIZE)
  const sourceX = Math.max(0, ((image.naturalWidth || sourceSize) - sourceSize) / 2)
  const sourceY = Math.max(0, ((image.naturalHeight || sourceSize) - sourceSize) / 2)

  context.clearRect(0, 0, LOGO_ANALYSIS_SIZE, LOGO_ANALYSIS_SIZE)
  context.drawImage(
    image,
    sourceX,
    sourceY,
    sourceSize,
    sourceSize,
    0,
    0,
    LOGO_ANALYSIS_SIZE,
    LOGO_ANALYSIS_SIZE,
  )

  const imageData = context.getImageData(0, 0, LOGO_ANALYSIS_SIZE, LOGO_ANALYSIS_SIZE)
  const center = LOGO_ANALYSIS_SIZE / 2
  const maxAllowedRadius = center
  let maxDistance = 0

  for (let y = 0; y < LOGO_ANALYSIS_SIZE; y += 1) {
    for (let x = 0; x < LOGO_ANALYSIS_SIZE; x += 1) {
      const dx = x + 0.5 - center
      const dy = y + 0.5 - center
      const distance = Math.sqrt(dx * dx + dy * dy)
      if (logoShape === 'circle' && distance > maxAllowedRadius) {
        continue
      }
      const alpha = imageData.data[(y * LOGO_ANALYSIS_SIZE + x) * 4 + 3]
      if (alpha < 10) {
        continue
      }
      if (distance > maxDistance) {
        maxDistance = distance
      }
    }
  }

  return maxDistance > 0 ? clamp(maxDistance / maxAllowedRadius, 0.2, 1) : 1
}

export function usePreviewAssetManager({
  backgroundSrc,
  logoEnabled,
  logoShape,
  logoSrc,
}: UsePreviewAssetManagerOptions): UsePreviewAssetManagerResult {
  const backgroundImageRef = useRef<HTMLImageElement | null>(null)
  const logoImageRef = useRef<HTMLImageElement | null>(null)
  const [backgroundLoadStatus, setBackgroundLoadStatus] = useState<PreviewAssetLoadStatus>('idle')
  const [logoLoadStatus, setLogoLoadStatus] = useState<PreviewAssetLoadStatus>('idle')
  const [logoVisibleRadiusRatio, setLogoVisibleRadiusRatio] = useState(1)

  useEffect(() => {
    if (!backgroundSrc) {
      backgroundImageRef.current = null
      setBackgroundLoadStatus('idle')
      return
    }

    let cancelled = false
    const loadStart = performance.now()
    const image = new Image()
    image.decoding = 'async'
    if (isRemoteAssetSource(backgroundSrc)) {
      image.crossOrigin = 'anonymous'
    }
    setBackgroundLoadStatus('loading')

    const handleReady = () => {
      if (!cancelled) {
        // #region debug-point A:background-decode-ready
        sendVideoPageLagDebug({
          hypothesisId: 'A',
          location: 'usePreviewAssetManager:background',
          msg: '[DEBUG] preview background image ready',
          data: {
            elapsedMs: Number((performance.now() - loadStart).toFixed(2)),
            width: image.naturalWidth,
            height: image.naturalHeight,
            sourcePrefix: backgroundSrc.slice(0, 32),
          },
        })
        // #endregion
        backgroundImageRef.current = image
        setBackgroundLoadStatus('ready')
      }
    }

    const handleError = () => {
      if (!cancelled) {
        // #region debug-point A:background-decode-error
        sendVideoPageLagDebug({
          hypothesisId: 'A',
          location: 'usePreviewAssetManager:background',
          msg: '[DEBUG] preview background image failed',
          data: {
            elapsedMs: Number((performance.now() - loadStart).toFixed(2)),
            sourcePrefix: backgroundSrc.slice(0, 32),
          },
        })
        // #endregion
        backgroundImageRef.current = null
        setBackgroundLoadStatus('error')
      }
    }

    image.onload = () => {
      if (typeof image.decode === 'function') {
        void image.decode().then(handleReady).catch(() => {
          if (image.naturalWidth > 0 && image.naturalHeight > 0) {
            handleReady()
            return
          }
          handleError()
        })
        return
      }
      handleReady()
    }
    image.onerror = handleError
    image.src = backgroundSrc
    if (image.complete && image.naturalWidth > 0 && image.naturalHeight > 0) {
      handleReady()
    }

    return () => {
      cancelled = true
    }
  }, [backgroundSrc])

  useEffect(() => {
    if (!logoSrc) {
      logoImageRef.current = null
      setLogoLoadStatus('idle')
      return
    }

    let cancelled = false
    const loadStart = performance.now()
    const image = new Image()
    image.decoding = 'async'
    if (isRemoteAssetSource(logoSrc)) {
      image.crossOrigin = 'anonymous'
    }
    setLogoLoadStatus('loading')

    const handleReady = () => {
      if (!cancelled) {
        // #region debug-point A:logo-decode-ready
        sendVideoPageLagDebug({
          hypothesisId: 'A',
          location: 'usePreviewAssetManager:logo',
          msg: '[DEBUG] preview logo image ready',
          data: {
            elapsedMs: Number((performance.now() - loadStart).toFixed(2)),
            width: image.naturalWidth,
            height: image.naturalHeight,
            sourcePrefix: logoSrc.slice(0, 32),
          },
        })
        // #endregion
        logoImageRef.current = image
        setLogoLoadStatus('ready')
      }
    }

    const handleError = () => {
      if (!cancelled) {
        // #region debug-point A:logo-decode-error
        sendVideoPageLagDebug({
          hypothesisId: 'A',
          location: 'usePreviewAssetManager:logo',
          msg: '[DEBUG] preview logo image failed',
          data: {
            elapsedMs: Number((performance.now() - loadStart).toFixed(2)),
            sourcePrefix: logoSrc.slice(0, 32),
          },
        })
        // #endregion
        logoImageRef.current = null
        setLogoLoadStatus('error')
      }
    }

    image.onload = () => {
      if (typeof image.decode === 'function') {
        void image.decode().then(handleReady).catch(() => {
          if (image.naturalWidth > 0 && image.naturalHeight > 0) {
            handleReady()
            return
          }
          handleError()
        })
        return
      }
      handleReady()
    }
    image.onerror = handleError
    image.src = logoSrc
    if (image.complete && image.naturalWidth > 0 && image.naturalHeight > 0) {
      handleReady()
    }

    return () => {
      cancelled = true
    }
  }, [logoSrc])

  useEffect(() => {
    if (!logoSrc || !logoEnabled) {
      setLogoVisibleRadiusRatio(1)
      return
    }

    let cancelled = false
    const measureStart = performance.now()
    void measureVisibleLogoRadiusRatio(logoSrc, logoShape)
      .then((nextRatio) => {
        if (!cancelled) {
          // #region debug-point A:logo-radius-analysis
          sendVideoPageLagDebug({
            hypothesisId: 'A',
            location: 'usePreviewAssetManager:logoRadius',
            msg: '[DEBUG] preview logo visible radius analysis completed',
            data: {
              elapsedMs: Number((performance.now() - measureStart).toFixed(2)),
              logoShape,
              visibleRadiusRatio: Number(nextRatio.toFixed(4)),
            },
          })
          // #endregion
          setLogoVisibleRadiusRatio(nextRatio)
        }
      })
      .catch(() => {
        if (!cancelled) {
          setLogoVisibleRadiusRatio(1)
        }
      })

    return () => {
      cancelled = true
    }
  }, [logoEnabled, logoShape, logoSrc])

  return {
    backgroundImageRef,
    backgroundLoadStatus,
    logoImageRef,
    logoLoadStatus,
    logoVisibleRadiusRatio,
  }
}
