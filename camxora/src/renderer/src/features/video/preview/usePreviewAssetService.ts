import type { MutableRefObject } from 'react'

import { usePreviewAssetManager, type PreviewAssetLoadStatus } from '@/features/video/preview/usePreviewAssetManager'
import { useRendererVideoPreview, type RendererPreviewCapability } from '@/features/video/useRendererVideoPreview'

type UsePreviewAssetServiceOptions = {
  backgroundPath: string
  logoEnabled: boolean
  logoPath: string
  logoShape: string
}

type UsePreviewAssetServiceResult = {
  backgroundImageRef: MutableRefObject<HTMLImageElement | null>
  backgroundLoadStatus: PreviewAssetLoadStatus
  backgroundSrc: string | null
  capability: RendererPreviewCapability
  logoImageRef: MutableRefObject<HTMLImageElement | null>
  logoLoadStatus: PreviewAssetLoadStatus
  logoSrc: string | null
  logoVisibleRadiusRatio: number
}

export function usePreviewAssetService({
  backgroundPath,
  logoEnabled,
  logoPath,
  logoShape,
}: UsePreviewAssetServiceOptions): UsePreviewAssetServiceResult {
  const { backgroundSrc, capability, logoSrc } = useRendererVideoPreview({
    backgroundPath,
    logoPath,
  })
  const {
    backgroundImageRef,
    backgroundLoadStatus,
    logoImageRef,
    logoLoadStatus,
    logoVisibleRadiusRatio,
  } = usePreviewAssetManager({
    backgroundSrc,
    logoEnabled,
    logoShape,
    logoSrc,
  })

  return {
    backgroundImageRef,
    backgroundLoadStatus,
    backgroundSrc,
    capability,
    logoImageRef,
    logoLoadStatus,
    logoSrc,
    logoVisibleRadiusRatio,
  }
}
